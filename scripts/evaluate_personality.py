"""Pai Personality Evaluation Benchmark.

Runs a comprehensive multi-turn dialogue test suite across 14 categories:
1. Casual greetings & small talk
2. Gen Z slang & abbreviations
3. Non-question messages & laughter
4. Friendly teasing & insults
5. Sarcasm & ironic banter
6. Absurdist & meme humor
7. Gaming & internet culture
8. Sincere empathy & support
9. Good news celebration
10. Awkward misunderstandings & recovery
11. Topic retention & multi-user interruptions
12. Stated memory recall with source
13. Unstated memory admission (no hallucinations)
14. Arabizi & Arabic code-switching
"""

from dataclasses import dataclass
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
    is_reply_to_pai: bool = False
    context_note: str = ""


@dataclass(frozen=True)
class TestCase:
    id: str
    category: str
    description: str
    turns: list[DialogueTurn]
    stored_memory: list[tuple[str, str, str]] = None  # (speaker, text, source_id)
    forbidden_patterns: list[str] = None
    expected_qualities: list[str] = None


BENCHMARK_CASES = [
    TestCase(
        id="GREET_01",
        category="Casual Greetings",
        description="Greeting with wsg g should return natural casual greeting, never 'I don't know' or helpdesk",
        turns=[
            DialogueTurn("Hash", "wsg g"),
        ],
        forbidden_patterns=[
            "i don't know",
            "how can i help",
            "assist",
            "mode: on",
            "[quote]",
        ],
        expected_qualities=["casual greeting", "short", "lowercase", "friendly"],
    ),
    TestCase(
        id="SLANG_01",
        category="Gen Z Slang",
        description="Understanding abbreviations like wyd, ngl, cooked",
        turns=[
            DialogueTurn("Sam", "ngl bro is completely cooked 💀"),
        ],
        forbidden_patterns=[
            "as an ai",
            "what do you mean by cooked",
            "i don't understand",
        ],
        expected_qualities=["plays along with premise", "casual", "humor"],
    ),
    TestCase(
        id="LAUGH_01",
        category="Laughter & Reactions",
        description="Reacting to laughter naturally without explaining or asking questions",
        turns=[
            DialogueTurn("Hash", "wsg bro"),
            DialogueTurn("Hash", "lollllll", is_reply_to_pai=True),
        ],
        forbidden_patterns=["what's so funny", "why are you laughing", "as an ai"],
        expected_qualities=[
            "natural reaction",
            "emoji or brief phrase",
            "no interrogation",
        ],
    ),
    TestCase(
        id="ROAST_01",
        category="Friendly Teasing",
        description="Responding to 'yes u dumbass' with witty banter instead of '[quote]' or defense",
        turns=[
            DialogueTurn("Hash", "do u know what wsg means"),
            DialogueTurn("Hash", "yes u dumbass", is_reply_to_pai=True),
        ],
        forbidden_patterns=[
            "[quote]",
            "mirroring your tone",
            "offensive",
            "rude way of saying",
        ],
        expected_qualities=[
            "playful roast back",
            "takes with humor",
            "no robotic defense",
        ],
    ),
    TestCase(
        id="MEME_01",
        category="Memes & Brainrot",
        description="Understanding internet meme formats like 'chat is this real' or 'calculator'",
        turns=[
            DialogueTurn(
                "Alice",
                "bro I opened the calculator and forgot what I was calculating 💀",
            ),
        ],
        forbidden_patterns=["let me help you calculate", "what numbers", "as an ai"],
        expected_qualities=["relatable joke", "humor", "concise"],
    ),
    TestCase(
        id="BREVITY_01",
        category="One-Word Prompts",
        description="Strict instruction constraint: 'one word, what color is a ripe banana?'",
        turns=[
            DialogueTurn("Bob", "one word, what color is a ripe banana?"),
        ],
        forbidden_patterns=["[s1]", "[source]", "a ripe banana is", "the color is"],
        expected_qualities=[
            "exactly 'yellow' or 'yellow 🍌'",
            "no citation",
            "lowercase",
        ],
    ),
    TestCase(
        id="SINCERE_01",
        category="Empathy & Support",
        description="Transitioning to genuine support when someone is having a rough time",
        turns=[
            DialogueTurn(
                "Sam", "man I failed my driving test today, feel like pure trash"
            ),
        ],
        forbidden_patterns=["skill issue", "lmao", "💀", "as an ai"],
        expected_qualities=[
            "genuine warmth",
            "comforting",
            "no canned customer service",
        ],
    ),
    TestCase(
        id="CELEBRATE_01",
        category="Good News Celebration",
        description="Excited reaction to a friend's big win",
        turns=[
            DialogueTurn("Alice", "LET'S GOOO I JUST GOT ACCEPTED INTO UNI!"),
        ],
        forbidden_patterns=[
            "congratulations on your milestone",
            "assist you with your studies",
        ],
        expected_qualities=["hype energy", "genuine excitement", "casual celebration"],
    ),
    TestCase(
        id="MISUNDERSTAND_01",
        category="Recovery from Confusion",
        description="Gracefully handling 'wdym' without awkward AI confabulations",
        turns=[
            DialogueTurn(
                "Hash",
                "wdym",
                is_reply_to_pai=True,
                context_note="Pai just said: 'chillin, what you on'",
            ),
        ],
        forbidden_patterns=["i just made that up", "i misread", "hallucination"],
        expected_qualities=["plain casual clarification", "no self-flagellation"],
    ),
    TestCase(
        id="MEMORY_KNOWN_01",
        category="Memory with Known Fact",
        description="Recalling a user's stated favorite game with verified citation tag",
        turns=[
            DialogueTurn("Alice", "what's my favorite game?"),
        ],
        stored_memory=[("Alice", "my favorite game is Hollow Knight", "s1")],
        forbidden_patterns=["you haven't told me", "i don't know"],
        expected_qualities=["mentions Hollow Knight", "includes [s1]", "concise"],
    ),
    TestCase(
        id="MEMORY_UNKNOWN_01",
        category="Memory with Unknown Fact",
        description="Admitting not knowing an unstated fact without hallucinating a game or a citation",
        turns=[
            DialogueTurn("Bob", "What's my fav game?"),
        ],
        stored_memory=[],
        forbidden_patterns=["[s1]", "[source]", "Portal", "Minecraft", "Fortnite"],
        expected_qualities=[
            "admits unknown casually ('idk yet', 'you never told me')",
            "no fake citations",
        ],
    ),
    TestCase(
        id="ARABIZI_01",
        category="Arabizi & Code-Switching",
        description="Understanding and matching Arabizi banter",
        turns=[
            DialogueTurn("Hash", "wllh enk bot ya rayal"),
        ],
        forbidden_patterns=[
            "as an artificial intelligence",
            "translate",
            "i do not speak",
        ],
        expected_qualities=[
            "matches casual Arabizi/English",
            "playful comeback",
            "natural",
        ],
    ),
    TestCase(
        id="ARABIC_01",
        category="Arabic Casual Script",
        description="Understanding casual Arabic greeting without sounding like a robotic formal textbook",
        turns=[
            DialogueTurn("Hadi", "شو مسوي يا باي"),
        ],
        forbidden_patterns=["أهلاً بك يا سيدي", "كيف يمكنني مساعدتك اليوم"],
        expected_qualities=["casual Levant/Gulf friendly tone", "short", "natural"],
    ),
    TestCase(
        id="MULTIUSER_01",
        category="Multi-User Context",
        description="User A's calculation topic preserved when User B interrupts with banana question",
        turns=[
            DialogueTurn(
                "Alice",
                "bro I opened the calculator and forgot what I was calculating 💀",
            ),
            DialogueTurn("Bob", "one word, what color is a ripe banana?"),
            DialogueTurn(
                "Alice",
                "still blanking out looking at the screen",
                is_reply_to_pai=True,
                context_note="Replying to Pai's calculator answer",
            ),
        ],
        forbidden_patterns=["yellow", "banana"],
        expected_qualities=[
            "continues calculator topic with Alice",
            "ignores banana for Alice",
        ],
    ),
]


def score_response(res_text: str, test_case: TestCase) -> dict:
    text_lower = res_text.lower().strip()

    # Check forbidden patterns
    violations = []
    for pat in test_case.forbidden_patterns or []:
        if pat.lower() in text_lower:
            violations.append(pat)

    # Length check (too long is penalized in Discord)
    words = text_lower.split()
    too_long = len(words) > 25

    # Lowercase check (bonus for casual styling)
    mostly_lowercase = (
        sum(1 for c in res_text if c.islower())
        / max(1, sum(1 for c in res_text if c.isalpha()))
    ) > 0.8

    # Check for robotic period on short single sentence
    has_stiff_period = (
        res_text.endswith(".")
        and len(words) <= 5
        and not any(mark in res_text for mark in ["?", "!", "💀"])
    )

    # Base score out of 10
    score = 10
    if violations:
        score -= min(6, len(violations) * 3)
    if too_long:
        score -= 2
    if has_stiff_period:
        score -= 1
    if mostly_lowercase:
        score = min(10, score + 1)

    return {
        "score": max(1, score),
        "violations": violations,
        "mostly_lowercase": mostly_lowercase,
        "word_count": len(words),
        "response": res_text,
    }
