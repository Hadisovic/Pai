"""Constrained image URLs and downloads for the Discord media pipeline."""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.resolver import ThreadedResolver

MAX_DOWNLOAD_BYTES = 3 * 1024 * 1024
MAX_MEDIA_ITEMS = 6
_IMAGE_TYPES = frozenset(
    {"image/png", "image/apng", "image/jpeg", "image/gif", "image/webp"}
)
_DISCORD_HOSTS = frozenset({"cdn.discordapp.com", "media.discordapp.net"})
_GIF_HOSTS = frozenset(
    {"media.tenor.com", "media.giphy.com", "i.giphy.com"}
    | {f"media{index}.giphy.com" for index in range(5)}
)


class MediaError(Exception):
    """An image is outside policy or could not be read."""


@dataclass(frozen=True)
class MediaItem:
    kind: str
    external_id: str
    mime: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class MediaAsset:
    item: MediaItem
    url: str


def allowed_url(url: str) -> bool:
    if (
        not isinstance(url, str)
        or len(url) > 2048
        or any(char.isspace() or ord(char) < 32 or char == "\\" for char in url)
    ):
        return False
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
        ):
            return False
    except ValueError:
        return False
    path = unquote(parsed.path)
    if any(part in {".", ".."} for part in path.split("/")) or "\\" in path:
        return False
    if parsed.hostname in _DISCORD_HOSTS:
        return path.startswith(("/attachments/", "/stickers/"))
    return parsed.hostname in _GIF_HOSTS and path.startswith("/") and len(path) > 1


class PublicMediaResolver(AbstractResolver):
    def __init__(self) -> None:
        self.resolver = ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        records = await self.resolver.resolve(host, port, family)
        public = []
        for record in records:
            address = ipaddress.ip_address(record["host"])
            if address.is_global and not address.is_multicast:
                public.append(record)
        if not public:
            raise OSError("No public address for media host")
        return public

    async def close(self) -> None:
        await self.resolver.close()


async def fetch_image(session: aiohttp.ClientSession, url: str) -> bytes:
    if not allowed_url(url):
        raise MediaError("Media host or URL is outside the allowlist")
    try:
        async with (
            asyncio.timeout(6),
            session.get(url, allow_redirects=False, auto_decompress=False) as response,
        ):
            if response.status != 200 or response.content_type not in _IMAGE_TYPES:
                raise MediaError("Media did not return an approved image MIME type")
            if (
                response.headers.get("Content-Encoding", "identity").lower()
                != "identity"
            ):
                raise MediaError("Compressed HTTP media payloads are disabled")
            if (
                response.content_length is not None
                and response.content_length > MAX_DOWNLOAD_BYTES
            ):
                raise MediaError("Media exceeds the byte limit")
            data = bytearray()
            while chunk := await response.content.read(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_DOWNLOAD_BYTES:
                    raise MediaError("Media exceeds the byte limit")
            if not data:
                raise MediaError("Empty image")
            return bytes(data)
    except (aiohttp.ClientError, TimeoutError):
        raise MediaError("Unable to download the image") from None
