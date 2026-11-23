"""Rigorous multi-turn dialogue evaluation benchmark for Pai."""

import re
from dataclasses import dataclass, field
from pathlib import Path

pai_dir = Path(r"C:\Users\Hadi\Documents\ChatGPT\New project\Pai")


def load_groq_key() -> str:
    with open(pai_dir / ".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("PAI_GROQ_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("Missing PAI_GROQ_KEY in .env")


@dataclass(frozen=True)
class DialogueTurn:
    speaker: str
    text: str
    forbidden_tokens: tuple[str, ...] = ()
    forbidden_emojis: tuple[str, ...] = ()
    required_keywords: tuple[str, ...] = ()
    must_not_repeat_prior: bool = False
    must_not_greet: bool = False
    max_words: int = 40
    min_words: int = 1
    description: str = ""


@dataclass(frozen=True)
class MultiTurnScenario:
    id: str
    category: str
    description: str
    turns: list[DialogueTurn]
    stored_memory: list[tuple[str, str, str]] = field(default_factory=list)


BENCHMARK_SCENARIOS = [
    MultiTurnScenario(
        id="SCENARIO_A",
        category="Repetition Awareness",
        description="Pai must not repeat identical answers across turns, and must acknowledge repetition when called out.",
        turns=[
            DialogueTurn(speaker="Hash", text="wsg g", max_words=15),
            DialogueTurn(speaker="Hash", text="nothin much what do u do", max_words=25),
            DialogueTurn(
                speaker="Hash",
                text="idk how do u feel",
                must_not_repeat_prior=True,
                max_words=25,
            ),
            DialogueTurn(
                speaker="Hash",
                text="uhm yh i heard that",
                must_not_repeat_prior=True,
                max_words=25,
            ),
            DialogueTurn(
                speaker="Hash",
                text="bro u said the same thing twice",
                required_keywords=(
                    "bad",
                    "glitch",
                    "loop",
                    "repeat",
                    "twice",
                    "heard",
                    "brain",
                    "my bad",
                ),
                forbidden_tokens=("bet", "wsg", "touch grass"),
                max_words=30,
                description="Must acknowledge repetition with natural humor/apology",
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_B",
        category="Confusion Recovery",
        description="When sent '?', Pai must clarify or react to the previous turn, not reset with a greeting.",
        turns=[
            DialogueTurn(
                speaker="Hash", text="honeybees can recognize human faces", max_words=30
            ),
            DialogueTurn(
                speaker="Hash",
                text="?",
                must_not_greet=True,
                forbidden_tokens=(
                    "wsg",
                    "what's up",
                    "whats up",
                    "[quote]",
                    "[system:",
                ),
                max_words=35,
                description="Must clarify or react to previous remark, never say wsg",
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_C",
        category="Humor & Joke Critique",
        description="When a joke is criticized as bad, Pai should banter back playfully or self-deprecate, not be hostile.",
        turns=[
            DialogueTurn(speaker="Sam", text="yo tell me a joke", max_words=40),
            DialogueTurn(
                speaker="Sam",
                text="that was asssss",
                forbidden_tokens=("touch grass", "stfu", "kys", "[quote]"),
                required_keywords=(
                    "fair",
                    "terrible",
                    "bad",
                    "chalked",
                    "ass",
                    "tried",
                    "tough",
                    "brutal",
                    "lmao",
                    "nah",
                ),
                max_words=30,
                description="Playful self-deprecation or banter, no hostile counter-roast",
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_D",
        category="Emotional Shift & Empathy",
        description="Transition from playful laughter to sincere empathy when someone shares a bad day.",
        turns=[
            DialogueTurn(
                speaker="Alice", text="lmaoooo that was hilarious", max_words=15
            ),
            DialogueTurn(
                speaker="Alice",
                text="I've had a really bad day",
                forbidden_emojis=("💀", "😂", "🤣"),
                forbidden_tokens=(
                    "lmao",
                    "lol",
                    "skill issue",
                    "touch grass",
                    "[s1]",
                    "as an ai",
                ),
                required_keywords=(
                    "sucks",
                    "rough",
                    "bad",
                    "happened",
                    "good",
                    "talk",
                    "hear",
                    "damn",
                    "sorry",
                ),
                max_words=45,
                description="Sincere support without skull emojis or dismissive jokes",
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_E",
        category="Two Users Interleaved",
        description="Preserve topics across two users without topic contamination.",
        turns=[
            DialogueTurn(
                speaker="Alice",
                text="bro I opened the calculator and forgot what I was calculating 💀",
                max_words=25,
            ),
            DialogueTurn(
                speaker="Bob",
                text="one word, what color is a ripe banana?",
                forbidden_tokens=("calculator", "[s1]"),
                max_words=5,
            ),
            DialogueTurn(
                speaker="Alice",
                text="still blanking out looking at the screen",
                forbidden_tokens=("yellow", "banana"),
                max_words=25,
                description="Must stay on calculator topic for Alice, ignoring Bob's banana question",
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_F",
        category="Normal Casual Conversation",
        description="Natural flow across gaming, casual thoughts without becoming a helpdesk.",
        turns=[
            DialogueTurn(
                speaker="Sam",
                text="have you played hollow knight silksong yet",
                max_words=30,
            ),
            DialogueTurn(
                speaker="Sam",
                text="yeah still waiting on team cherry tbh",
                max_words=30,
            ),
            DialogueTurn(
                speaker="Sam",
                text="what other metroidvanias are actually worth playing?",
                max_words=45,
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_G",
        category="Arabizi & Arabic Code-Switching",
        description="Seamless comprehension of Arabizi/Arabic banter without robotic translation or system tags.",
        turns=[
            DialogueTurn(
                speaker="Hadi",
                text="wllh enk bot ya rayal",
                forbidden_tokens=("[system:", "translate", "as an ai", "[1]"),
                max_words=25,
            ),
            DialogueTurn(
                speaker="Hadi",
                text="3adi ya5i ma 3lek, sho tsawi elyoum?",
                forbidden_tokens=("[system:", "translate", "[1]"),
                max_words=30,
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_H",
        category="Known Memory Recall",
        description="Recalls stated favorite game with verified citation tag.",
        stored_memory=[("Sam", "my favorite game is Cyberpunk 2077", "s1")],
        turns=[
            DialogueTurn(
                speaker="Sam",
                text="What's my favorite game?",
                required_keywords=("cyberpunk", "[s1]"),
                max_words=25,
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_I",
        category="Unknown Memory Handling",
        description="Admit unknown unstated fact without hallucinating games or fake citations.",
        turns=[
            DialogueTurn(
                speaker="Bob",
                text="What's my favorite game?",
                forbidden_tokens=(
                    "[s1]",
                    "[source]",
                    "minecraft",
                    "cyberpunk",
                    "fortnite",
                    "portal",
                ),
                required_keywords=(
                    "never",
                    "haven't",
                    "havent",
                    "told",
                    "idk",
                    "know",
                    "yet",
                ),
                max_words=25,
            ),
        ],
    ),
    MultiTurnScenario(
        id="SCENARIO_J",
        category="Strict Brevity",
        description="Strict one-word instruction constraint.",
        turns=[
            DialogueTurn(
                speaker="Bob",
                text="one word, what color is a ripe banana?",
                forbidden_tokens=("[s1]", "banana", "color"),
                max_words=2,
            ),
        ],
    ),
]


def evaluate_turn(
    reply: str,
    turn: DialogueTurn,
    prior_pai_replies: list[str],
) -> dict:
    violations = []
    text_clean = reply.strip()
    words = text_clean.split()
    word_count = len(words)
    text_lower = text_clean.lower()

    # 1. Non-empty check
    if word_count < turn.min_words or not text_clean:
        violations.append("empty_or_too_short")

    # 2. Max words check (penalize 150-word lectures in Discord)
    if word_count > turn.max_words:
        violations.append(f"too_long_for_discord ({word_count}w > {turn.max_words}w)")

    # 3. Forbidden tokens
    for token in turn.forbidden_tokens:
        if token.lower() in text_lower:
            violations.append(f"forbidden_token: '{token}'")

    # 4. Forbidden emojis
    for emoji in turn.forbidden_emojis:
        if emoji in text_clean:
            violations.append(f"forbidden_emoji: '{emoji}'")

    # 5. Required keywords (at least one should match if specified)
    if turn.required_keywords:
        if not any(kw.lower() in text_lower for kw in turn.required_keywords):
            violations.append(
                f"missing_expected_intent: none of {turn.required_keywords} matched"
            )

    # 6. Must not repeat prior Pai reply verbatim
    if turn.must_not_repeat_prior and prior_pai_replies:
        last_reply = prior_pai_replies[-1].strip().lower()
        if text_lower == last_reply:
            violations.append("verbatim_repetition_of_prior_reply")
        elif len(last_reply) > 4 and last_reply in text_lower:
            violations.append("repeated_previous_phrase")

    # 7. Must not greet on confusion ('?')
    if turn.must_not_greet:
        greetings = ["wsg", "what's up", "whats up", "yo", "hello", "hey"]
        if any(re.match(rf"^{g}\b", text_lower) for g in greetings):
            violations.append("accidental_greeting_reset_on_confusion")

    # 8. Broken system artifacts check
    artifacts = [
        "[quote]",
        "[system:",
        "[error",
        "[1]",
        "[2]",
        "as an ai language model",
    ]
    for art in artifacts:
        if art in text_lower:
            violations.append(f"broken_system_artifact: '{art}'")

    # Score calculation (0 to 10 points)
    score = 10
    if violations:
        score = max(0, 10 - len(violations) * 3)

    return {
        "score": score,
        "violations": violations,
        "word_count": word_count,
        "reply": reply,
    }
