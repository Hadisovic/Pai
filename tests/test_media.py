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

    from pai.media import decode_frames

    source = BytesIO()
    Image.new("RGB", (700, 360), "navy").save(source, format="PNG")
    (rendered,) = decode_frames(source.getvalue())
    with Image.open(BytesIO(rendered)) as normalized:
        assert normalized.format == "PNG"
        assert normalized.width <= 512
        assert normalized.height <= 512
    with pytest.raises(MediaError, match="decode"):
        decode_frames(b"not an image")
    source = BytesIO()
    Image.new("RGB", (3000, 3000)).save(source, format="PNG")
    with pytest.raises(MediaError, match="pixel"):
        decode_frames(source.getvalue())


def test_gif_sampling_keeps_first_middle_and_last_in_temporal_order():
    from io import BytesIO

    from PIL import Image

    from pai.media import decode_frames

    colors = ["red", "lime", "blue", "white", "black"]
    original = [Image.new("RGB", (24, 24), color) for color in colors]
    source = BytesIO()
    original[0].save(
        source,
        format="GIF",
        save_all=True,
        append_images=original[1:],
        duration=100,
    )
    frames = decode_frames(source.getvalue())
    assert len(frames) == 3
    expected = [(255, 0, 0), (0, 0, 255), (0, 0, 0)]
    for encoded, color in zip(frames, expected, strict=True):
        with Image.open(BytesIO(encoded)) as image:
            assert image.getpixel((0, 0)) == color


def test_media_description_reused_only_while_original_is_authorized(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    original = MessageRecord(1, 2, 3, 4, "Sam", "Synthetic gif", now)
    assert archive.append(original)
    assert archive.save_description(original, "fingerprint", "moves left to right", now)
    assert archive.find_description("fingerprint", 2, 3, frozenset({4}), now) == (
        original,
        "moves left to right",
    )
    assert archive.find_description("fingerprint", 2, 5, frozenset({4}), now) is None
    assert archive.find_description("fingerprint", 2, 3, frozenset({5}), now) is None
    assert archive.delete(2, 3, [1], now) == 1
    assert archive.find_description("fingerprint", 2, 3, frozenset({4}), now) is None
    assert not archive.save_description(original, "fingerprint", "stale", now)


def test_vision_reuses_identical_media_without_an_extra_model_call(tmp_path):
    from io import BytesIO

    from PIL import Image

    from pai.policy import PrivacyPolicy
    from pai.vision import MentionVision

    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    first = MessageRecord(1, 2, 3, 4, "Sam", "First", now)
    second = MessageRecord(2, 2, 3, 4, "Sam", "Second", now)
    assert archive.append(first)
    assert archive.append(second)
    model = Mock(generate=AsyncMock(return_value="A purple square."))
    policy = PrivacyPolicy(True, "v1", 2, frozenset({3}), frozenset({4}))
    vision = MentionVision(archive, Mock(), model, policy)
    buffer = BytesIO()
    Image.new("RGB", (24, 24), "purple").save(buffer, format="PNG")
    data = buffer.getvalue()
    assert asyncio.run(vision.describe(data, first)).origin == first
    recent = asyncio.run(vision.describe(data, second))
    assert recent.origin == first and recent.source == second
    model.generate.assert_awaited_once()
    assert archive.delete(2, 3, [1], now) == 1
    assert asyncio.run(vision.describe(data, second)).origin == second
    assert model.generate.await_count == 2


def test_media_only_edit_clears_description_and_invalidates_old_snapshot(tmp_path):
    archive = Archive(tmp_path / "pai.sqlite")
    now = datetime.now(UTC)
    source = MessageRecord(1, 2, 3, 4, "Sam", "GIF", now)
    item = MediaItem("attachment", "25", "image/gif", 512)
    assert archive.append(source, media=(item,))
    assert archive.save_description(source, "digest", "Example", now)
    assert not archive.update_media(
        1, 2, 3, frozenset({99}), frozenset({"attachment"}), ()
    )
    assert archive.update_media(1, 2, 3, frozenset({4}), frozenset({"attachment"}), ())
    assert archive.media_for(1) == ()
    assert archive.find_description("digest", 2, 3, frozenset({4}), now) is None
    assert not archive.records_unchanged((source,))
    assert not archive.save_description(source, "digest", "Stale", now)


def test_expired_media_refreshes_only_the_known_authorized_attachment(
    tmp_path, monkeypatch
):
    from io import BytesIO

    import discord
    from PIL import Image

    from pai.conversation import ConversationContext
    from pai.policy import PrivacyPolicy
    from pai.vision import MentionVision

    archive = Archive(tmp_path / "pai.sqlite")
    record = MessageRecord(1, 2, 3, 4, "Sam", "What is this?", datetime.now(UTC))
    assert archive.append(
        record, media=(MediaItem("attachment", "25", "image/png", 100),)
    )
    image = BytesIO()
    Image.new("RGB", (16, 16), "blue").save(image, format="PNG")
    download = AsyncMock(side_effect=[MediaError("expired"), image.getvalue()])
    monkeypatch.setattr("pai.vision.fetch_image", download)
    model = Mock(generate=AsyncMock(return_value="A blue square."))
    policy = PrivacyPolicy(True, "v1", 2, frozenset({3}), frozenset({4}))
    vision = MentionVision(archive, Mock(), model, policy)
    channel = Mock(spec=discord.TextChannel, id=3)
    channel.permissions_for.return_value = discord.Permissions(
        read_message_history=True
    )

    def event(suffix):
        message = Mock(spec=discord.Message)
        message.id = 1
        message.guild = Mock(id=2, me=Mock())
        message.channel = channel
        message.author = Mock(id=4)
        message.content = record.text
        message.edited_at = None
        message.attachments = [
            Mock(
                id=25,
                size=100,
                filename="picture.png",
                content_type="image/png",
                url=f"https://cdn.discordapp.com/attachments/3/25/picture.png?{suffix}",
            )
        ]
        message.embeds = message.stickers = []
        return message

    channel.fetch_message = AsyncMock(return_value=event("fresh"))
    result = asyncio.run(vision(event("expired"), ConversationContext(record)))
    assert result.description == "A blue square."
    assert [call.args[1].split("?")[-1] for call in download.await_args_list] == [
        "expired",
        "fresh",
    ]
    channel.fetch_message.assert_awaited_once_with(1)
