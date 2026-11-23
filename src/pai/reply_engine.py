"""Pai's English-first, source-aware Discord reply behavior."""

from pai.conversation import ConversationContext
from pai.model_router import NoFreeRoute, NoUsableReply, Router
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
            response = await self.router.generate(
                prompt.request, render=lambda raw: render_answer(raw, prompt)
            )
        except NoUsableReply:
            return ""
        except NoFreeRoute:
            return self.notice.unavailable(channel)
        self.notice.recovered(channel)
        return response
