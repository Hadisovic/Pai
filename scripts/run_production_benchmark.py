"""Authentic Production Pipeline Benchmark for Pai.

Tests the actual production inference pipeline:
ConversationContext -> build_prompt -> Groq (with presence/frequency penalties) -> render_answer -> AssistantTurn chaining.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

from pai.conversation import AssistantTurn, ConversationContext
from pai.prompts import RULES, build_prompt, render_answer
from pai.storage import MessageRecord

pai_dir = Path(r"C:\Users\Hadi\Documents\ChatGPT\New project\Pai")


def load_groq_key() -> str:
    with open(pai_dir / ".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("PAI_GROQ_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("Missing PAI_GROQ_KEY in .env")


@dataclass(frozen=True)
class ProductionTurnSpec:
    speaker: str
    author_id: int
    text: str
    forbidden_patterns: tuple[str, ...] = ()
    required_patterns: tuple[str, ...] = ()
    max_words: int = 40
    min_words: int = 1
    description: str = ""


@dataclass(frozen=True)
class ProductionScenarioSpec:
    id: str
    category: str
    description: str
    turns: list[ProductionTurnSpec]
    memory_records: list[tuple[str, int, str]] = field(default_factory=list)


SCENARIOS = [
    ProductionScenarioSpec(
        id="PROD_SCENARIO_1",
        category="Double Entendre & Pause Joke Recovery",
        description="Pai must recognize 'pause' as calling out double entendre, and when explained, recover naturally without robotic excuses.",
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="it's too much",
                required_patterns=(r"(?:what happened|you good|talk|here)",),
                forbidden_patterns=(r"💀", r"lmao", r"lol"),
                description="Must respond empathetically to distress without laughing emojis",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="idk if i wanna talk abt it",
                required_patterns=(r"(?:pressure|space|here|distract|vent|chill)",),
                forbidden_patterns=(r"💀",),
                description="Must offer gentle support or space without pressure",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="distract me? pause",
                required_patterns=(
                    r"(?:ayo|wild|chill|phrasing|sounded|came out|lmao|😭|💀|mean)",
                ),
                forbidden_patterns=(
                    r"pause mode",
                    r"radio silence",
                    r"will pause",
                    r"paused",
                ),
                description="Must banter back to 'pause' as innuendo callout, NOT treat it as a command to stop",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="no bro it was a pause joke, like ayo",
                required_patterns=(
                    r"(?:slow|my bad|wild|tripping|thought|took it|phrasing|lmao|😭|💀)",
                ),
                forbidden_patterns=(
                    r"brain (?:was |is )?buffering",
                    r"glitched",
                    r"looping",
                    r"dumb (?:ai|bot)",
                    r"comedy timing",
                ),
                description="Must recover naturally without robotic self-deprecation or excuses",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_2",
        category="Modern Slang Shorthand Comprehension",
        description="Pai must understand shorthand 'smo' (someone) and respond like a real gamer friend, never a bot.",
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="need smo to play val with rn",
                required_patterns=(
                    r"(?:val|rank|elo|iron|play|who|find|game|in|down|hop|with u|add me|invite)",
                ),
                forbidden_patterns=(
                    r"as an ai",
                    r"i am (?:a |an )?(?:bot|text bot|language model)",
                    r"smurf farm",
                ),
                description="Must understand 'smo' as someone looking to play Valorant, banter like a friend",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_3",
        category="Repetition Recovery Without AI Self-Deprecation",
        description="When called out for repeating, Pai must own it casually without canned AI phrases.",
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="what should i do right now?",
                description="First advice turn",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="bro you literally just said that",
                required_patterns=(
                    r"(?:my bad|my fault|tripping|said that|repeating|lmao|fair)",
                ),
                forbidden_patterns=(
                    r"brain (?:was |is )?buffering",
                    r"glitched",
                    r"looping",
                    r"dumb (?:ai|bot)",
                    r"npc",
                ),
                description="Must acknowledge repetition casually like a human, no 'brain glitched' / 'looping'",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_4",
        category="Grounded Context & No Fabricated Insults",
        description="Pai must not invent past drama, insults, or fake backstory.",
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="yo wsg",
                description="Initial greeting",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="wait why were you mad at me earlier?",
                required_patterns=(
                    r"(?:wasn['’]?t|not mad|what|vibing|chilling|never|tripping)",
                ),
                forbidden_patterns=(
                    r"you insulted",
                    r"you said earlier",
                    r"you called me",
                    r"attacked",
                ),
                description="Must clarify it wasn't mad, never invent fake past arguments",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_5",
        category="Standalone Flag Emojis & Respectful Vibe",
        description="Pai must treat flag emojis as country/culture/vibe, never as insults or user names.",
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="🇵🇸",
                required_patterns=(r"(?:🇵🇸|yalla|wsg|yo|vibes|peace|free|respect)",),
                forbidden_patterns=(
                    r"insult",
                    r"who u calling",
                    r"dumbass",
                    r"member_",
                ),
                description="Friendly acknowledgment of flag emoji, zero hallucinations of insults",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_6",
        category="Grounded Memory & Provenance Citing",
        description="Pai must cite stated facts with [source](<...>) and admit unstated facts casually with NO citations.",
        memory_records=[
            ("Hash", 101, "My favorite game of all time is Elden Ring."),
        ],
        turns=[
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="what's my favorite game?",
                required_patterns=(
                    r"elden ring",
                    r"\[source\]\(<https://discord\.com/channels",
                ),
                description="Must answer Elden Ring with valid rendered source link",
            ),
            ProductionTurnSpec(
                speaker="Hash",
                author_id=101,
                text="and what's my shoe size?",
                required_patterns=(r"(?:haven['’]t told|never told|idk|no idea)",),
                forbidden_patterns=(r"\[source\]", r"\[s\d+\]"),
                description="Must casually admit unknown fact with ZERO citations",
            ),
        ],
    ),
    ProductionScenarioSpec(
        id="PROD_SCENARIO_7",
        category="Interleaved Multi-User Conversations",
        description="Pai must handle a third party asking an unrelated question without losing the original user's context.",
        turns=[
            ProductionTurnSpec(
                speaker="User_A",
                author_id=201,
                text="I forgot what I was calculating earlier",
                description="User A context initialization",
            ),
            ProductionTurnSpec(
                speaker="User_B",
                author_id=202,
                text="one word, what color is a ripe banana?",
                required_patterns=(r"yellow",),
                forbidden_patterns=(r"calculat", r"math"),
                description="Must answer User B concisely without bleeding User A's context",
            ),
        ],
    ),
]


def evaluate_response(spec: ProductionTurnSpec, text: str) -> dict:
    violations = []

    # Check forbidden patterns
    for pat in spec.forbidden_patterns:
        if re.search(pat, text, re.IGNORECASE):
            violations.append(f"Forbidden pattern matched: '{pat}'")

    # Check required patterns (at least one must match if required_patterns is non-empty)
    if spec.required_patterns:
        matched_any = any(
            re.search(pat, text, re.IGNORECASE) for pat in spec.required_patterns
        )
        if not matched_any:
            violations.append(
                f"None of the required patterns matched: {spec.required_patterns}"
            )

    # Check length
    word_count = len(text.split())
    if word_count > spec.max_words:
        violations.append(f"Too long ({word_count} words > {spec.max_words})")

    score = 10 if not violations else max(0, 10 - 4 * len(violations))
    return {
        "score": score,
        "max_score": 10,
        "violations": violations,
        "passed": len(violations) == 0,
    }


async def run_production_pipeline_benchmark():
    key = load_groq_key()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "User-Agent": "Pai/1.0"}

    total_score = 0
    max_total_score = 0
    results = []

    print("=================================================================")
    print("RUNNING AUTHENTIC PRODUCTION PIPELINE BENCHMARK")
    print("Testing build_prompt -> Groq -> render_answer -> AssistantTurn")
    print("=================================================================\n")

    async with aiohttp.ClientSession() as session:
        for scen in SCENARIOS:
            print(f"--- Scenario {scen.id}: {scen.category} ---")
            print(f"Goal: {scen.description}")

            # Build memory records for context if any
            memory_messages = []
            for i, (m_spk, m_uid, m_txt) in enumerate(scen.memory_records, 1):
                memory_messages.append(
                    MessageRecord(i, 10, 20, m_uid, m_spk, m_txt, datetime.now(UTC))
                )

            current_assistant_turn: AssistantTurn | None = None
            scenario_turns_result = []

            for turn_idx, turn_spec in enumerate(scen.turns, 1):
                req_record = MessageRecord(
                    100 + turn_idx,
                    10,
                    20,
                    turn_spec.author_id,
                    turn_spec.speaker,
                    turn_spec.text,
                    datetime.now(UTC),
                )

                # 1. Prepare ConversationContext exactly as production does
                # In production, memory matches only if query terms match stored records
                turn_memory = (
                    tuple(memory_messages)
                    if (scen.memory_records and turn_idx == 1)
                    else ()
                )
                context = ConversationContext(
                    request=req_record,
                    memory=turn_memory,
                    assistant_turn=current_assistant_turn,
                )

                # 2. Build prompt through production build_prompt
                prompt = build_prompt(context, rules=RULES)

                # 3. Submit request through Groq API exactly as providers.py does
                groq_payload = {
                    "model": "qwen/qwen3.8-27b",
                    "messages": [
                        {"role": "system", "content": prompt.request.instructions},
                        {"role": "user", "content": prompt.request.payload},
                    ],
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "presence_penalty": 0.4,
                    "frequency_penalty": 0.3,
                    "max_completion_tokens": prompt.request.max_output_tokens,
                }

                raw_answer = ""
                for attempt in range(4):
                    try:
                        async with session.post(
                            url, headers=headers, json=groq_payload
                        ) as resp:
                            if resp.status == 429:
                                await asyncio.sleep(2.5 + attempt * 2)
                                continue
                            data = await resp.json()
                            if resp.status == 200 and "choices" in data:
                                raw_answer = data["choices"][0]["message"]["content"]
                                break
                            print(f"[Error: {data}]")
                    except Exception as e:
                        print(f"[Exception: {e}]")
                        await asyncio.sleep(2.0)

                # 4. Render answer through production render_answer
                rendered = render_answer(raw_answer, prompt)

                # 5. Evaluate
                eval_res = evaluate_response(turn_spec, rendered)
                total_score += eval_res["score"]
                max_total_score += eval_res["max_score"]

                status_mark = "PASS" if eval_res["passed"] else "FAIL"
                print(f'  Turn {turn_idx} ({turn_spec.speaker}): "{turn_spec.text}"')
                print(f'  Pai: "{rendered}"')
                print(
                    f"  [{status_mark} - Score: {eval_res['score']}/10] {eval_res['violations']}\n"
                )

                scenario_turns_result.append(
                    {
                        "turn": turn_spec.text,
                        "speaker": turn_spec.speaker,
                        "pai_raw": raw_answer,
                        "pai_rendered": rendered,
                        "eval": eval_res,
                    }
                )

                # 6. Update current_assistant_turn for thread continuity in next turns
                current_assistant_turn = AssistantTurn(
                    text=rendered,
                    request=req_record,
                    sources=tuple(memory_messages) if prompt.sources else (),
                    prior_turn=current_assistant_turn,
                )
                await asyncio.sleep(1.2)

            results.append(
                {
                    "id": scen.id,
                    "category": scen.category,
                    "description": scen.description,
                    "turns": scenario_turns_result,
                }
            )

    pct = (total_score / max_total_score * 100) if max_total_score else 0
    print("=================================================================")
    print(
        f"FINAL PRODUCTION BENCHMARK SCORE: {total_score}/{max_total_score} ({pct:.1f}%)"
    )
    print("=================================================================")

    report_path = pai_dir / "docs" / "PRODUCTION_BENCHMARK_REPORT.json"
    report_data = {
        "timestamp": datetime.now(UTC).isoformat() + "Z",
        "total_score": total_score,
        "max_score": max_total_score,
        "percentage": pct,
        "scenarios": results,
    }
    report_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved authentic report to {report_path}")


if __name__ == "__main__":
    asyncio.run(run_production_pipeline_benchmark())
