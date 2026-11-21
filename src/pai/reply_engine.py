"""Pai's English-first, source-aware Discord reply behavior."""

from pai.conversation import ConversationContext
from pai.model_router import NoFreeRoute, Router
from pai.prompts import RULES, build_prompt, render_answer
from pai.providers import OutageNotice

_PERSONALITY = (
    "Default to natural English. Try to understand Arabic and Arabizi. Reply in another "
    "language when asked. Be warm and brief. Follow the room's humor when it fits, keep "
    "teasing gentle, and drop a style if someone asks. Avoid forced slang or catchphrases."
)


class ReplyEngine:
    def __init__(self, router: Router) -> None:
        self.router = router
        self.notice = OutageNotice()

    async def __call__(self, context: ConversationContext) -> str:
        prompt = build_prompt(
            context, frames=context.media.frames, rules=f"{RULES} {_PERSONALITY}"
        )
        channel = context.request.channel_id
        try:
            response = await self.router.generate(prompt.request)
        except NoFreeRoute:
            return self.notice.unavailable(channel)
        self.notice.recovered(channel)
        return render_answer(response, prompt)
