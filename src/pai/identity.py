"""Scoped identity answers with trusted configuration and no model call."""

import json
import re
from dataclasses import dataclass
from datetime import timedelta

from pai.conversation import ConversationContext
from pai.policy import PrivacyPolicy
from pai.runtime_info import BuildInfo, _query

_CREATOR = "Hadisovic"
_TOPICS = {
    "creator": r"who (?:made|built|created|developed|coded) (?:you|u|pai)"
    r"|who(?:['’]s| is) (?:your|ur) (?:creator|developer)"
    r"|(?:مين|من) (?:عملك|صنعك|برمجك|طورك|طوّرك)|min (?:3amalak|barmajak)",
    "identity": r"who (?:are (?:you|u)|is pai)|what are (?:you|u)"
    r"|what(?:['’]s| is) (?:your|ur) name|(?:مين|شو) (?:انت|إنت|أنت|اسمك)",
    "model": r"are (?:you|u) (?:qwen|gpt(?:-oss)?)"
    r"|(?:what|which) model (?:are u(?: (?:on|using))?|do u use)"
    r"|شو (?:الموديل|النموذج) (?:تبعك|اللي بتستخدمه)",
    "fallback": r"(?:(?:what(?:['’]s| is) )?(?:your|ur) fallback(?: model)?"
    r"|which fallback(?: model)? (?:do (?:you|u) use|is configured))",
    "memory": r"do (?:you|u) (?:remember (?:our (?:chat|conversations)|(?:this|the) chat)"
    r"|have (?:persistent |long-term )?memory)"
    r"|(?:شو|ايش) بتتذكر من (?:الدردشة|الشات)|بتتذكر (?:حكينا|محادثاتنا)",
    "learning": r"do (?:you|u) learn from (?:our |this |the )?(?:chat|messages|conversations)"
    r"|بتتعلم من (?:الحكي|الدردشة|الشات)",
}
_QUESTION = re.compile(
    r"^(?:(?:hey|yo|pai)[, ]+)?(?:"
    + "|".join(f"(?P<{topic}>{pattern})" for topic, pattern in _TOPICS.items())
    + r")$",
    re.IGNORECASE,
)
_FALLBACK_FOLLOWUP = re.compile(
    r"(?:and|what about) (?:the |your |ur )?fallback(?: model)?", re.IGNORECASE
)
_INDIRECT = re.compile(
    r"\bbehind (?:this|the) (?:account|bot)\b|\bbehind (?:you|u|pai)\b"
    r"|\b(?:qwen|gpt(?:-oss)?)\b.{0,55}\b(?:built|made|creator|person|human|model|developer)\b"
    r"|\b(?:built|made|trained|created) (?:you|u|pai)\b.{0,55}\b(?:qwen|gpt|human|person)\b"
    r"|\b(?:who's|who is) the (?:human|person|one) (?:who|that)\b.{0,45}\b(?:you|u|pai|ur)\b"
    r"|\b(?:are|were) (?:you|u) (?:actually|really) (?:a person|human|a bot)\b"
    r"|\b(?:انت|إنت|أنت) (?:مجرد موديل|إنسان ولا|انسان ولا)|(?:مين|من) ورا (?:البوت|الحساب)",
    re.IGNORECASE,
)
_INDIRECT_FOLLOWUP = re.compile(
    r"^(?:so|then|and) (?:what does that make (?:you|u)|who made (?:you|u)|who's the person)$",
    re.IGNORECASE,
)
_SELF_REFERENCE = re.compile(
    r"\b(?:you|u|your|ur|pai|(?:this|the) (?:bot|account)|انت|إنت|أنت|البوت|الحساب)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Identity:
    policy: PrivacyPolicy
    text_routes: tuple[str, ...]
    build: BuildInfo | None = None

    def prompt_facts(self, context: ConversationContext, read_history: bool) -> str:
        request = context.request
        if not self.policy.permits(
            request.guild_id, request.channel_id, request.author_id
        ) or (context.style and context.style.situation):
            return ""
        query = _query(request.text)
        prior = context.assistant_turn
        followup = (
            read_history
            and prior is not None
            and prior.request.author_id == request.author_id
            and timedelta(0)
            <= request.created_at - prior.request.created_at
            <= timedelta(minutes=10)
            and _INDIRECT_FOLLOWUP.fullmatch(query)
            and (
                _QUESTION.fullmatch(_query(prior.request.text))
                or _INDIRECT.search(_query(prior.request.text))
            )
        )
        if not (
            (_INDIRECT.search(query) and _SELF_REFERENCE.search(query)) or followup
        ):
            return ""
        facts = {
            "name": "Pai",
            "role": "AI-powered Discord friend and companion",
            "human_creator": _CREATOR,
            "primary_text_model": self.text_routes[0] if self.text_routes else None,
            "fallback_text_model": self.text_routes[1]
            if len(self.text_routes) > 1
            else None,
            "release": self.build.release if self.build else None,
            "revision": self.build.revision if self.build else None,
            "authorized_channel_recall": read_history,
            "social_learning_for_speaker": read_history
            and self.policy.permits_social(
                request.guild_id, request.channel_id, request.author_id
            ),
            "channel_media_analysis_enabled": self.policy.media_opt_in,
            "limitations": "No browsing, private account access, code execution or physical control.",
        }
        return "Verified Pai runtime facts:\n" + json.dumps(
            facts, ensure_ascii=False, separators=(",", ":")
        )

    def reply(
        self, context: ConversationContext, read_history: bool = True
    ) -> str | None:
        request = context.request
        if not self.policy.permits(
            request.guild_id, request.channel_id, request.author_id
        ):
            return None
        query = _query(request.text)
        match = _QUESTION.fullmatch(query)
        topic = match.lastgroup if match else None
        prior = context.assistant_turn
        if (
            topic is None
            and _FALLBACK_FOLLOWUP.fullmatch(query)
            and prior is not None
            and prior.request.author_id == request.author_id
            and timedelta(0)
            <= request.created_at - prior.request.created_at
            <= timedelta(minutes=10)
        ):
            previous = _QUESTION.fullmatch(_query(prior.request.text))
            if previous and previous.lastgroup in {"identity", "model", "fallback"}:
                topic = "fallback"
        if topic is None:
            return None

        language = context.style.language if context.style else ""
        if not language and re.search(r"[\u0621-\u064a]", query):
            language = "arabic"
        elif not language and re.match(r"min (?:3amalak|barmajak)$", query, re.I):
            language = "arabizi"

        def say(english: str, arabic: str, arabizi: str) -> str:
            return {"arabic": arabic, "arabizi": arabizi}.get(language, english)

        learning = self.policy.permits_social(
            request.guild_id, request.channel_id, request.author_id
        )
        primary = self.text_routes[0] if self.text_routes else None
        fallback = self.text_routes[1] if len(self.text_routes) > 1 else None
        if topic == "creator":
            return say(
                f"{_CREATOR} made me.", f"{_CREATOR} عملني.", f"{_CREATOR} 3amalni."
            )
        if topic == "identity":
            return say(
                "i'm Pai, your Discord companion.",
                "أنا Pai، رفيقكم عالديسكورد.",
                "ana Pai, rafi2kom 3al Discord.",
            )
        if topic == "model":
            if not primary:
                return say(
                    "there's no text model on here.",
                    "ما عندي موديل نص مفعّل.",
                    "ma 3andi model lal text hon.",
                )
            return say(
                f"i'm Pai. {primary} is my default text model.",
                f"أنا Pai. موديل النص الأساسي {primary}.",
                f"ana Pai. {primary} howwe el model el asasi lal text.",
            )
        if topic == "fallback":
            if not fallback:
                return say(
                    "there's no fallback configured here.",
                    "ما عندي موديل احتياطي هون.",
                    "ma 3andi fallback hon.",
                )
            return say(
                f"{fallback} is my text fallback.",
                f"الموديل الاحتياطي {fallback}.",
                f"el fallback taba3i {fallback}.",
            )
        if topic == "memory":
            if not read_history:
                return say(
                    "i can't read the old chat here rn.",
                    "ما بقدر أرجع للشات القديم هون.",
                    "ma ba2dar arja3 lal chat el adeem hon.",
                )
            return say(
                "i can recall saved messages people agreed to share here.",
                "بقدر أتذكر الرسائل المسموح أحفظها هون.",
                "ba2dar atzakkar el rasa2el el masmoo7 a7fazha hon.",
            )
        if learning and read_history:
            return say(
                "i can pick up group meanings people opted in to share here.",
                "بتعلم معاني من المساهمات المسموحة هون.",
                "bat3allam ma3ani men el mosahamat el masmoo7a hon.",
            )
        return say(
            "social learning's off for me here.",
            "التعلّم من الشات مطفّى عندي هون.",
            "el ta3allom men el chat mtaffi 3andi hon.",
        )
