"""Extract bounded metadata from authorized Discord messages."""

from hashlib import sha256
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import discord

from pai.media import (
    MAX_DOWNLOAD_BYTES,
    MAX_MEDIA_ITEMS,
    MediaAsset,
    MediaItem,
    allowed_url,
)

_IMAGE_SUFFIXES = frozenset({".png", ".apng", ".jpg", ".jpeg", ".gif", ".webp"})


def discover_media(message: discord.Message) -> tuple[MediaAsset, ...]:
    assets = []
    for attachment in message.attachments:
        if (
            attachment.size <= MAX_DOWNLOAD_BYTES
            and PurePosixPath(attachment.filename).suffix.lower() in _IMAGE_SUFFIXES
            and allowed_url(attachment.url)
        ):
            item = MediaItem(
                "attachment",
                str(attachment.id),
                attachment.content_type,
                attachment.size,
            )
            assets.append(MediaAsset(item, attachment.url))
    for sticker in message.stickers:
        if sticker.format == discord.StickerFormatType.lottie or not allowed_url(
            sticker.url
        ):
            continue
        assets.append(MediaAsset(MediaItem("sticker", str(sticker.id)), sticker.url))
    for embed in message.embeds:
        for url in (embed.image.url, embed.thumbnail.url):
            if url and allowed_url(url):
                parts = urlsplit(url)
                id_value = sha256(f"{parts.hostname}{parts.path}".encode()).hexdigest()
                assets.append(MediaAsset(MediaItem("embed", id_value), url))
                break
    unique = {asset.item.external_id: asset for asset in assets}
    return tuple(unique.values())[:MAX_MEDIA_ITEMS]
