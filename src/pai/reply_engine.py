"""Pai's English-first, source-aware Discord reply behavior."""

from pai.conversation import ConversationContext, requests_personal_event
from pai.model_router import NoFreeRoute, NoUsableReply, Router
from pai.prompts import build_prompt, recall_evidence, render_answer
from pai.providers import OutageNotice
from pai.runtime_info import BuildInfo, runtime_reply


class ReplyEngine:
    def __init__(
        self, router: Router, *, build: BuildInfo | None = None, vision: bool = False
    ) -> None:
        self.router = router
        self.build = build
        self.vision = vision
        self.primary_model = next(
            (route.name for route in router.routes if route.verified_free), None
        )
        self.notice = OutageNotice()

    async def __call__(self, context: ConversationContext) -> str:
        fact = runtime_reply(
            context, self.build, vision=self.vision, primary_model=self.primary_model
        )
        if fact is not None:
            return fact
        if (
            requests_personal_event(context.request.text)
            and not (context.memory or context.parents)
            and (context.style is None or context.style.situation != "imminent")
        ):
            return "idk, i don’t have anything to go on."
        prompt = build_prompt(context)
        channel = context.request.channel_id
        try:
            response = await self.router.generate(
                prompt.request,
                render=lambda raw: render_answer(raw, prompt, vision=self.vision),
            )
        except NoUsableReply:
            return ""
        except NoFreeRoute:
            return self.notice.unavailable(channel)
        self.notice.recovered(channel)
        if (
            context.self_recall
            and "[source](<" not in response
            and not (context.style and context.style.situation == "imminent")
        ):
            return recall_evidence(context, prompt)
        return response
