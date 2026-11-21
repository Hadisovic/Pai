"""Pai's English-first, source-aware Discord reply behavior."""

from pai.conversation import ConversationContext
from pai.model_router import NoFreeRoute, Router
from pai.prompts import RULES, build_prompt, render_answer
from pai.providers import OutageNotice

_PERSONALITY = (
    "Default to natural, conversational English. Understand Arabic and Arabizi when used. "
    "Reply in another language when asked. Keep responses short and punchy (1 to 2 sentences max, like a real Discord user). "
    "Match the room's energy and participate in the group's humor and light banter without forcing it. "
    "Adapt naturally to whoever is speaking to you without copying one person's habits or repeating jokes constantly."
)


class ReplyEngine:
    def __init__(self, router: Router) -> None:
        self.router = router
        self.notice = OutageNotice()

    async def __call__(self, context: ConversationContext) -> str:
        prompt = build_prompt(context, rules=f"{RULES} {_PERSONALITY}")
        channel = context.request.channel_id
        try:
            response = await self.router.generate(prompt.request)
        except NoFreeRoute:
            return self.notice.unavailable(channel)
        self.notice.recovered(channel)
        return render_answer(response, prompt)
