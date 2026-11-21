"""Select one current or directly replied-to image per authorized mention."""

import asyncio

import aiohttp
import discord

from pai.conversation import ConversationContext
from pai.discord_media import discover_media
from pai.media import MediaError, MediaReading, decode_still, fetch_image
from pai.storage import Archive


class MentionVision:
    def __init__(self, archive: Archive, session: aiohttp.ClientSession) -> None:
        self.archive = archive
        self.session = session

    async def __call__(
        self, message: discord.Message, context: ConversationContext
    ) -> MediaReading:
        candidates = [(context.request, message)]
        if context.parents:
            parent = context.parents[0]
            reference = message.reference
            resolved = reference.resolved if reference is not None else None
            candidates.append((parent, resolved))
        for record, candidate in candidates:
            stored = await asyncio.to_thread(self.archive.media_for, record.message_id)
            if not stored:
                continue
            if (
                not isinstance(candidate, discord.Message)
                or candidate.id != record.message_id
                or candidate.channel.id != record.channel_id
                or candidate.author.id != record.author_id
            ):
                return MediaReading(unavailable=True)
            known = {(item.kind, item.external_id) for item in stored}
            asset = next(
                (
                    asset
                    for asset in discover_media(candidate)
                    if (asset.item.kind, asset.item.external_id) in known
                ),
                None,
            )
            if asset is None:
                return MediaReading(unavailable=True)
            try:
                data = await fetch_image(self.session, asset.url)
                return MediaReading((await asyncio.to_thread(decode_still, data),))
            except MediaError:
                return MediaReading(unavailable=True)
        return MediaReading()
