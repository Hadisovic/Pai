"""Pai's English-first, source-aware Discord reply behavior."""

from pai.conversation import ConversationContext
from pai.model_router import NoFreeRoute, Router
from pai.prompts import build_prompt, render_answer
from pai.providers import OutageNotice


class ReplyEngine:
    def __init__(self, router: Router) -> None:
        self.router = router
        self.notice = OutageNotice()

    async def __call__(self, context: ConversationContext) -> str:
        prompt = build_prompt(context)
        channel = context.request.channel_id
        try:
            response = await self.router.generate(prompt.request)
        except NoFreeRoute:
            return self.notice.unavailable(channel)
        self.notice.recovered(channel)
        return render_answer(response, prompt) or "i lost the thread for a sec"
