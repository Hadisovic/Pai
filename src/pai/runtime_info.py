"""Verified runtime facts for narrow, locally answered self-report questions."""

import re
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from pai.conversation import ConversationContext, _normalized_request

_REVISION = re.compile(r"[0-9a-f]{40}")
_RELEASE = re.compile(r"^(P[0-9]+(?:\.[0-9]+)+):", re.IGNORECASE)
_BUILD = re.compile(
    r"^(?:(?:hey|yo|pai)[, ]+)?(?:"
    r"(?:what|which) (?:software |current )?(?:version|build|release|commit) (?:are you|is pai)"
    r"(?: (?:on|running|using|rn|right now))*"
    r"|what(?:['’]s| is) (?:your|pai['’]s) (?:current )?(?:version|build|release|commit)"
    r"|what (?:version|build|release|commit) (?:do you run|did you deploy|of pai is running)"
    r"|(?:show|give|tell) me (?:your|the) (?:running |deployed )?(?:version|build|release|commit)"
    r"|(?:your )?(?:running |deployed )?(?:version|build|release|commit)"
    r"|(?:شو|ايش|إيش|وش|شنو) (?:إصدارك|اصدارك|نسختك))$",
    re.IGNORECASE,
)
_DETAIL = re.compile(
    r"^(?:(?:and|so|wait)[, ]+)?(?:what(?:['’]s| is) (?:that|it)"
    r"|what do (?:you|u) mean|which one|what version|of what|what['’]s the full (?:sha|commit)"
    r"|(?:v?[0-9]+(?:\.[0-9]+)+|p[0-9]+(?:\.[0-9]+)+) (?:of what|means what))$",
    re.IGNORECASE,
)
_CAPABILITY = re.compile(
    r"^(?:can|do|are) (?:you|u)(?: able to| have the ability to)? "
    r"(?P<tool>(?:(?:browse|search|access|use) (?:the )?(?:web|internet)|browse online|go online)"
    r"|(?:(?:see|read|understand|analyze|analyse|view) (?:an? )?(?:images?|gifs?|pictures?|photos?))"
    r"|(?:(?:run|execute) code|access my (?:dms|direct messages)|read my (?:dms|direct messages)))$",
    re.IGNORECASE,
)
_MODEL = re.compile(
    r"^(?:(?:what|which) (?:ai |text )?model (?:are you(?: (?:on|using|running))?"
    r"|do you use|is pai using)|what(?:['’]s| is) your (?:default |text )?model)$",
    re.IGNORECASE,
)
_ONLINE = re.compile(
    r"^(?:are (?:you|u) (?:online|live|deployed)(?: (?:right now|rn|here))?"
    r"|where (?:are you|is pai) (?:running|deployed))$",
    re.IGNORECASE,
)
_SELF_VERSION_CLAIM = re.compile(
    r"\b(?:i(?:['’]m| am) (?:currently )?(?:running|on|using)"
    r"|(?:my|pai['’]s) (?:current |software )?(?:version|build|release)"
    r"|i (?:was|have been) deployed)\b.{0,48}"
    r"\b(?:v?[0-9]+\.[0-9]+|p[0-9]+\.[0-9]+|stable|latest|production|test(?:ing)?|chatgpt|gpt[-‑]?[0-9]+)\b",
    re.IGNORECASE,
)


_TOOL_CLAIM = re.compile(
    r"\bi (?:(?:can|could|will) (?:browse|search|use|access) (?:the )?(?:web|internet)"
    r"|(?:can|could|will) (?:execute|run) (?:your |this )?code"
    r"|(?:can|could|will) (?:read|access) (?:your )?(?:dms|direct messages)"
    r"|(?:ran|executed) (?:your|the|this) code|(?:read|opened) your (?:dms|direct messages))\b",
    re.IGNORECASE,
)
_VISION_CLAIM = re.compile(
    r"\bi (?:can|could|will) (?:see|read|analyze|analyse|view|open)"
    r" (?:your |the |this )?(?:images?|gifs?|pictures?|photos?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BuildInfo:
    revision: str
    release: str = ""


def capture_build() -> BuildInfo | None:
    """Resolve the installed source's clean Git tree once for this process."""
    source = Path(__file__).resolve()
    checkout = source.parents[2]

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(checkout), *args],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            timeout=3,
        ).stdout.strip()

    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != checkout:
            return None
        git("ls-files", "--error-unmatch", source.relative_to(checkout).as_posix())
        revision = git("rev-parse", "--verify", "HEAD")
        if not _REVISION.fullmatch(revision) or git(
            "status", "--porcelain", "--untracked-files=no", "--", "src/pai"
        ):
            return None
        release = _RELEASE.match(git("show", "-s", "--format=%s", revision))
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    return BuildInfo(revision, release[1] if release else "")


def _query(text: str) -> str:
    return _normalized_request(text).rstrip("?.!؟").strip()


def _build_followup(context: ConversationContext, text: str) -> bool:
    if not _DETAIL.fullmatch(text):
        return False
    turn = context.assistant_turn
    request = context.request
    for _ in range(4):
        if (
            turn is None
            or turn.request.author_id != request.author_id
            or not timedelta(0)
            <= request.created_at - turn.request.created_at
            <= timedelta(minutes=10)
        ):
            return False
        earlier = _query(turn.request.text)
        if _BUILD.fullmatch(earlier):
            return True
        if not _DETAIL.fullmatch(earlier):
            return False
        turn = turn.prior_turn
    return False


def runtime_reply(
    context: ConversationContext,
    build: BuildInfo | None,
    *,
    vision: bool,
    primary_model: str | None,
) -> str | None:
    text = _query(context.request.text)
    followup = _build_followup(context, text)
    if _BUILD.fullmatch(text) or followup:
        if build is None:
            return "i can't verify which build is running."
        if build.release and not followup and "commit" not in text.casefold():
            return f"{build.release.lower()} rn"
        return f"pai's running commit is {build.revision}"
    if _MODEL.fullmatch(text):
        return (
            f"my default text model here is {primary_model}."
            if primary_model
            else "i can't verify the default text model here."
        )
    if _ONLINE.fullmatch(text):
        return "i'm online in this Discord channel rn."
    capability = _CAPABILITY.fullmatch(text)
    if capability is None:
        return None
    tool = capability["tool"].casefold()
    if any(word in tool for word in ("web", "internet", "online")):
        return "i can't browse the web from Discord."
    if any(word in tool for word in ("images", "image", "gif", "picture", "photo")):
        return (
            "i can read images and GIFs i can access in this channel."
            if vision
            else "image and GIF analysis is off here."
        )
    if tool.endswith("code"):
        return "i can talk through code, but i can't run it from Discord."
    return "i can't read your DMs."


def unsupported_runtime_claim(text: str, *, vision: bool) -> bool:
    return bool(
        _SELF_VERSION_CLAIM.search(text)
        or _TOOL_CLAIM.search(text)
        or (not vision and _VISION_CLAIM.search(text))
    )
