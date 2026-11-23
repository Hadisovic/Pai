"""Scoped bot settings and per-turn social cues. Contains no inferred user profiles."""

import re
from dataclasses import dataclass

STYLE_OPTIONS = {
    "language": frozenset({"auto", "english", "arabic", "arabizi"}),
    "tone": frozenset({"auto", "casual", "gentle"}),
    "emoji": frozenset({"auto", "off"}),
}

_EMOJI_OFF = re.compile(
    r"\b(?:no |without |stop (?:using|with )|(?:don['’]?t|do not) (?:use|send) )"
    r"(?:\s*(?:that|this|the|any|more))?\s*emoji(?:e?s|e)?\b|^\s*(?:the )?emoji(?:e?s)[.!?]*\s*$",
    re.IGNORECASE,
)
_EMOJI_AUTO = re.compile(
    r"\b(?:emojis? (?:are |is )?(?:fine|ok(?:ay)?)|use emojis again)\b", re.IGNORECASE
)
_LANGUAGE_REQUEST = re.compile(
    r"\b(?:(?:answer|reply|respond|say (?:it|that)|write) in|jaw[ie]b (?:bel|bil)) (english|arabic|arabizi)\b",
    re.IGNORECASE,
)
_STOP_BIT = re.compile(
    r"^\s*(?:seriously,?\s+)?(?:stop(?: the (?:joke|bit|roast))?|drop the (?:attitude|bit|joke)|jokes aside|no more jokes)\b",
    re.IGNORECASE,
)
_FIRSTHAND_DANGER = re.compile(
    r"\b(?:i(?:['’]?m| am)\s+(?:going to|about to)\s+(?:kill|hurt|harm) myself"
    r"|i (?:will|might) (?:kill|hurt|harm) myself"
    r"|i(?:['’]?ve| have) (?:a |the )?noose (?:around|on) my neck"
    r"|i (?:just |already )?(?:cut|hurt|harmed) myself)\b",
    re.IGNORECASE,
)
_BOT_TAUNT = re.compile(r"^\s*(?:go die|kill yourself|kys)[.!?]*\s*$", re.IGNORECASE)
_WEB_REQUEST = re.compile(
    r"\b(?:browse|search|check|look (?:it |this )?up) (?:the )?(?:web|internet|online)"
    r"|\b(?:source|sources|link|links)\b.{0,36}\b(?:web|internet|online)\b"
    r"|\b(?:search|google) (?:for |it\b)",
    re.IGNORECASE,
)
_WEB_CLAIM = re.compile(
    r"\b(?:i (?:searched|checked|looked up|found|verified)|according to)\b.{0,70}\b(?:web|internet|online|google|wikipedia)\b"
    r"|\baccessed\s+\d{1,2}\s+\w+\s+\d{4}\b|\[link omitted\]",
    re.IGNORECASE,
)
_GROUP_REQUEST = re.compile(
    r"\b(?:each of us|all of us|everyone (?:here|in (?:the|this) (?:chat|channel))|who(?:['’]s| is) (?:here|in (?:the|this) (?:chat|channel)))\b",
    re.IGNORECASE,
)
_EMOJI = re.compile(
    r"(?:[0-9#*]\ufe0f?\u20e3|[\U0001F1E6-\U0001F1FF]{2}|"
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\u2764]\ufe0f?[\U0001F3FB-\U0001F3FF]?"
    r"(?:\u200d[\U0001F300-\U0001FAFF\u2600-\u27BF\u2764]\ufe0f?[\U0001F3FB-\U0001F3FF]?)*"
    r")"
)


@dataclass(frozen=True)
class ReplyStyle:
    language: str = ""
    tone: str = ""
    emoji_off: bool = False
    situation: str = ""
    web_requested: bool = False


def reply_style(
    text: str,
    settings: dict[str, str],
    recent_own: tuple[str, ...] = (),
    danger_own: tuple[str, ...] = (),
) -> ReplyStyle:
    language = _LANGUAGE_REQUEST.search(text)
    emoji_off = settings.get("emoji") == "off"
    for line in (text, *recent_own):
        if _EMOJI_OFF.search(line):
            emoji_off = True
            break
        if _EMOJI_AUTO.search(line):
            emoji_off = False
            break
    situation = ""
    if any(_FIRSTHAND_DANGER.search(line) for line in (text, *danger_own)):
        situation = "imminent"
    elif _BOT_TAUNT.fullmatch(text):
        situation = "bot_directed"
    elif _STOP_BIT.search(text):
        situation = "stop"
    return ReplyStyle(
        language[1].lower() if language else settings.get("language", ""),
        "" if situation in {"imminent", "stop"} else settings.get("tone", ""),
        emoji_off or situation == "imminent",
        situation,
        bool(_WEB_REQUEST.search(text)),
    )


def requests_group(text: str) -> bool:
    return bool(_GROUP_REQUEST.search(text))


def unsupported_web_claim(text: str) -> bool:
    return bool(_WEB_CLAIM.search(text))


def remove_emoji(text: str) -> str:
    return _EMOJI.sub("", text).strip()
