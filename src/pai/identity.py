"""Scoped identity answers with trusted configuration and no model call."""

import re
from dataclasses import dataclass
from datetime import timedelta

from pai.conversation import ConversationContext
from pai.policy import PrivacyPolicy
from pai.runtime_info import _query

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


@dataclass(frozen=True)
class Identity:
    policy: PrivacyPolicy
    text_routes: tuple[str, ...]

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
        arabic = language == "arabic" or (
            not language and re.search(r"[\u0621-\u064a]", query) is not None
        )
        learning = self.policy.permits_social(
            request.guild_id, request.channel_id, request.author_id
        )
        primary = self.text_routes[0] if self.text_routes else None
        fallback = self.text_routes[1] if len(self.text_routes) > 1 else None
        if topic == "creator":
            return f"{_CREATOR} عملني." if arabic else f"{_CREATOR} made me."
        if topic == "identity":
            return (
                "أنا Pai، رفيقكم عالديسكورد."
                if arabic
                else "i'm Pai, your Discord companion."
            )
        if topic == "model":
            if not primary:
                return (
                    "ما عندي موديل نص مفعّل."
                    if arabic
                    else "there's no text model on here."
                )
            return (
                f"أنا Pai. موديل النص الأساسي {primary}."
                if arabic
                else f"i'm Pai. {primary} is my default text model."
            )
        if topic == "fallback":
            if not fallback:
                return (
                    "ما عندي موديل احتياطي هون."
                    if arabic
                    else "there's no fallback configured here."
                )
            return (
                f"الموديل الاحتياطي {fallback}."
                if arabic
                else f"{fallback} is my text fallback."
            )
        if topic == "memory":
            if not read_history:
                return (
                    "ما بقدر أرجع للشات القديم هون."
                    if arabic
                    else "i can't read the old chat here rn."
                )
            return (
                "بقدر أتذكر الرسائل المسموح أحفظها هون."
                if arabic
                else "i can recall saved messages people agreed to share here."
            )
        if learning and read_history:
            return (
                "بتعلم معاني من المساهمات المسموحة هون."
                if arabic
                else "i can pick up group meanings people opted in to share here."
            )
        return (
            "التعلّم من الشات مطفّى عندي هون."
            if arabic
            else "social learning's off for me here."
        )
