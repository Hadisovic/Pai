import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from pai.media import (
    MAX_DOWNLOAD_BYTES,
    MediaError,
    MediaItem,
    allowed_url,
    fetch_image,
)
from pai.storage import Archive, MessageRecord

GIF_URL = "https://media.tenor.com/example/animation.gif"


@pytest.mark.parametrize(
    "url",
    [
        "http://media.tenor.com/x.gif",
        "https://media.tenor.com.bad.example/x.gif",
        "https://media.tenor.com@127.0.0.1/x.gif",
        "https://user@media.tenor.com/x.gif",
        "https://media.tenor.com:8443/x.gif",
        "https://127.0.0.1/x.png",
        "https://images-ext-1.discordapp.net/external/anything",
        "https://cdn.discordapp.com/api/v10/anything",
        "https://cdn.discordapp.com/attachments/../anything",
        "https://cdn.discordapp.com/attachments/%2e%2e/anything",
    ],
)
def test_media_allowlist_rejects_unsafe_or_unapproved_urls(url):
    assert not allowed_url(url)


def test_download_skips_redirects_and_rejects_over_budget_before_reading():
    assert allowed_url(GIF_URL)
    response = Mock(
        status=200, content_type="image/gif", content_length=MAX_DOWNLOAD_BYTES + 1
    )
    response.headers = {}
    response.content.read = AsyncMock()
    request = AsyncMock()
    request.__aenter__.return_value = response
    session = Mock()
    session.get.return_value = request
    with pytest.raises(MediaError, match="byte limit"):
        asyncio.run(fetch_image(session, GIF_URL))
    assert session.get.call_args.kwargs["allow_redirects"] is False
    response.content.read.assert_not_awaited()


def test_media_metadata_stores_identifiers_without_signed_urls_and_cascades(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    message = MessageRecord(1, 2, 3, 4, "Sam", "Synthetic", now)
    items = (MediaItem("attachment", "25", "image/gif", 512),)
    assert archive.append(message, media=items)
    assert archive.media_for(1) == items
    assert archive.delete(2, 3, [1], now) == 1
    assert archive.media_for(1) == ()


def test_decoding_validates_actual_format_and_pixel_count():
    from io import BytesIO

    from PIL import Image

    from pai.media import decode_still

    source = BytesIO()
    Image.new("RGB", (700, 360), "navy").save(source, format="PNG")
    rendered = decode_still(source.getvalue())
    with Image.open(BytesIO(rendered)) as normalized:
        assert normalized.format == "PNG"
        assert normalized.width <= 512
        assert normalized.height <= 512
    with pytest.raises(MediaError, match="decode"):
        decode_still(b"not an image")
    source = BytesIO()
    Image.new("RGB", (3000, 3000)).save(source, format="PNG")
    with pytest.raises(MediaError, match="pixel"):
        decode_still(source.getvalue())
