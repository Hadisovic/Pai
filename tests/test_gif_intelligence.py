from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace as NS

import pytest
from PIL import Image

from pai.gif_media import decode_animation, discover_gifs
from pai.gif_store import GifStore
from pai.media import MediaError
from pai.policy import PrivacyPolicy
from pai.storage import Archive, MessageRecord


def fixture_gif():
    images = [Image.new("RGB", (32, 32), color) for color in ("red", "blue", "green")]
    out = BytesIO()
    images[0].save(
        out, format="GIF", save_all=True, append_images=images[1:], duration=140
    )
    return out.getvalue()


def test_gif_picker_and_uploaded_animation_are_ordered():
    msg = NS(
        attachments=[
            NS(
                size=200,
                filename="react.gif",
                url="https://cdn.discordapp.com/attachments/1/2/react.gif",
                id=2,
                content_type="image/gif",
            )
        ],
        content="https://tenor.com/view/a-shared-reaction-555",
        embeds=[
            NS(
                type="gifv",
                video=NS(url="https://media.tenor.com/x/tenor.mp4", proxy_url=None),
                image=NS(url=None, proxy_url=None),
                thumbnail=NS(
                    url="https://media.tenor.com/x/poster.jpg", proxy_url=None
                ),
            )
        ],
    )
    assets = discover_gifs(msg)
    assert [asset.url for asset in assets] == [
        msg.attachments[0].url,
        msg.embeds[0].video.url,
    ]
    frames, filename = decode_animation(fixture_gif(), "image/gif")
    assert filename.endswith(".gif")
    assert [Image.open(BytesIO(frame)).getpixel((0, 0)) for frame in frames] == [
        (255, 0, 0),
        (0, 0, 255),
        (0, 128, 0),
    ]
    out = BytesIO()
    Image.new("RGB", (16, 16)).save(out, "GIF")
    with pytest.raises(MediaError):
        decode_animation(out.getvalue(), "image/gif")


def test_gif_sources_are_scoped_deduplicated_and_revocable(tmp_path):
    policy = PrivacyPolicy(
        True,
        "v1",
        1,
        frozenset({2}),
        frozenset({3, 4}),
        external_ai_opt_in=True,
        gif_reuse_opt_in=True,
        gif_consenting_member_ids=frozenset({3}),
    )
    now = datetime.now(UTC)
    path = tmp_path / "archive.sqlite"
    archive = Archive(path)
    lib = GifStore(archive, policy)
    first = MessageRecord(10, 1, 2, 3, "M", "quiet confusion", now)
    duplicate = MessageRecord(11, 1, 2, 3, "M", "quiet disbelief", now)
    unauthorized = MessageRecord(12, 1, 2, 4, "N", "quiet disbelief", now)
    for item in (first, duplicate, unauthorized):
        archive.append(item)
    assert lib.remember(first, "one", "a" * 64, "quiet confusion and disbelief")
    assert lib.remember(
        duplicate, "two", "a" * 64, lib.description(duplicate, "a" * 64)
    )
    assert not lib.remember(unauthorized, "secret", "b" * 64, "quiet confusion")
    reopened = GifStore(Archive(path), policy)
    matches = reopened.candidates(duplicate, "quiet disbelief")
    assert len(matches) == 1 and matches[0].fingerprint == "a" * 64
    assert matches[0].source.message_id in (10, 11)
    archive.delete(1, 2, (10, 11), now)
    assert not reopened.candidates(duplicate, "quiet disbelief")


def _gif_context(tmp_path):
    policy = PrivacyPolicy(
        True,
        "gif-v1",
        1,
        frozenset({2}),
        frozenset({3, 4}),
        external_ai_opt_in=True,
        gif_reuse_opt_in=True,
        gif_consenting_member_ids=frozenset({3, 4}),
    )
    arc = Archive(tmp_path / "gif.sqlite")
    return arc, GifStore(arc, policy), policy


@pytest.mark.parametrize(
    ("completion", "expected", "selected"),
    [
        ("[gif:g1]", "", True),
        ("yeah that's disbelief\n[gif:g1]", "yeah that's disbelief", True),
        ("nice try\n[gif:g999]", "nice try", False),
        ("two?\n[gif:g1]\n[gif:g1]", "two?", False),
        ("yeah that's rough", "yeah that's rough", False),
    ],
)
def test_model_selects_only_offered_gif_ids(tmp_path, completion, expected, selected):
    import asyncio
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from pai.conversation import prepare_context
    from pai.gifs import GifFeature
    from pai.model_router import ProviderRoute, Quota, Router
    from pai.reply_engine import ReplyEngine

    arc, store, policy = _gif_context(tmp_path)
    now = datetime.now(UTC)
    source = MessageRecord(
        10, 1, 2, 3, "M", "absolute disbelief", now - timedelta(minutes=50)
    )
    arc.append(source)
    store.remember(
        source, "asset", "a" * 64, "A pretend expression of quiet disbelief."
    )
    request = MessageRecord(11, 1, 2, 4, "N", "still in disbelief", now)
    ask = AsyncMock(return_value=completion)
    route = ProviderRoute("fixture", 3, True, Quota(25, 800, 8000, 180000), ask)
    feature = GifFeature(
        store,
        None,
        ReplyEngine(Router(arc, (route,)), conversation_engine="timeline-roles"),
    )
    out = asyncio.run(
        feature.respond(prepare_context(arc, policy, request, timeline=True), True)
    )
    assert out.text == expected and (out.entry is not None) is selected
    assert ask.await_count == 1
    assert "Optional verified GIF options" in ask.call_args.args[0].payload


def test_reuse_fetches_exact_original_bytes_and_fails_closed(tmp_path, monkeypatch):
    import asyncio
    from hashlib import sha256
    from unittest.mock import AsyncMock, Mock

    import discord

    from pai.gif_media import GifAsset
    from pai.gifs import GifFeature
    from pai.model_router import Router
    from pai.reply_engine import ReplyEngine

    arc, store, _ = _gif_context(tmp_path)
    url = "https://cdn.discordapp.com/attachments/1/2/f.gif"
    body = fixture_gif()
    now = datetime.now(UTC)
    source = MessageRecord(10, 1, 2, 3, "M", "disbelief", now)
    req = MessageRecord(11, 1, 2, 4, "N", "still in disbelief", now)
    arc.append(source)
    arc.append(req)
    assert store.remember(
        source, GifAsset(url).identity, sha256(body).hexdigest(), "disbelief"
    )
    entry = store.entry(source)
    channel = Mock(spec=discord.TextChannel, id=2, guild=Mock(id=1, me=object()))
    channel.permissions_for.return_value = discord.Permissions.all()
    msg = NS(
        id=10,
        author=NS(id=3, bot=False),
        webhook_id=None,
        guild=channel.guild,
        channel=channel,
        content=source.text,
        edited_at=None,
        attachments=[
            NS(size=len(body), filename="f.gif", url=url, content_type="image/gif")
        ],
        embeds=[],
    )
    channel.fetch_message = AsyncMock(return_value=msg)
    fetch = AsyncMock(return_value=(body, "image/gif"))
    monkeypatch.setattr("pai.gifs.fetch_media", fetch)
    feature = GifFeature(store, None, ReplyEngine(Router(arc, ())))
    file = asyncio.run(feature.attachment(channel, req, entry))
    assert file and file.filename == "reaction.gif" and file.fp.read() == body
    file.close()
    fetch.return_value = (body + b"wrong", "image/gif")
    assert asyncio.run(feature.attachment(channel, req, entry)) is None
    from pai.media import MediaError

    fetch.side_effect = MediaError("expired")
    assert asyncio.run(feature.attachment(channel, req, entry)) is None
    arc.delete(1, 2, (source.message_id,), now)
    assert asyncio.run(feature.attachment(channel, req, entry)) is None
    assert fetch.await_count == 3


def test_index_analyzes_duplicate_once_and_copes_with_no_free_route(
    tmp_path, monkeypatch
):
    import asyncio
    from unittest.mock import AsyncMock

    from pai.gifs import GifFeature
    from pai.model_router import NoFreeRoute, ProviderRoute, Quota, Router
    from pai.reply_engine import ReplyEngine

    arc, store, _ = _gif_context(tmp_path)
    now = datetime.now(UTC)
    body = fixture_gif()
    fetch = AsyncMock(return_value=(body, "image/gif"))
    monkeypatch.setattr("pai.gifs.fetch_media", fetch)

    def make(mid):
        source = MessageRecord(mid, 1, 2, 3, "M", "original reaction", now)
        arc.append(source)
        return source, NS(
            id=mid,
            author=NS(id=3, bot=False),
            webhook_id=None,
            guild=NS(id=1),
            channel=NS(id=2),
            content=source.text,
            edited_at=None,
            embeds=[],
            attachments=[
                NS(
                    size=len(body),
                    filename="f.gif",
                    url=f"https://cdn.discordapp.com/attachments/2/{mid}/f.gif",
                    content_type="image/gif",
                )
            ],
        )

    a, m1 = make(10)
    b, m2 = make(11)
    complete = AsyncMock(
        return_value='{"description":"The swatch changes.","reusable":true}'
    )
    route = ProviderRoute("vision", 3, True, Quota(25, 800, 8000, 180000), complete)
    with_route = GifFeature(store, None, ReplyEngine(Router(arc, (route,))))
    asyncio.run(with_route.index(m1.channel, 10, m1))
    asyncio.run(with_route.index(m2.channel, 11, m2))
    assert len(complete.call_args.args[0].frames) == 2
    assert complete.await_count == 1
    assert store.entry(a).fingerprint == store.entry(b).fingerprint
    assert "The swatch changes." == store.entry(b).description
    no_route = GifFeature(store, None, ReplyEngine(Router(arc, ())))
    with pytest.raises(NoFreeRoute):
        asyncio.run(no_route.caption((b"frame",), "fixture"))
    assert complete.await_count == 1
    from dataclasses import replace

    arc.apply_policy(replace(store.policy, gif_consenting_member_ids=frozenset({4})))
    assert store.entry(a) is None and store.entry(b) is None


def test_video_representation_uses_ordered_bounded_frames(tmp_path):
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        pytest.skip("Optional FFmpeg binaries not installed")
    gif = tmp_path / "fixture.gif"
    video = tmp_path / "fixture.mp4"
    gif.write_bytes(fixture_gif())
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-i",
            str(gif),
            "-an",
            "-c:v",
            "mpeg4",
            str(video),
        ],
        check=True,
        timeout=10,
    )
    frames, filename = decode_animation(video.read_bytes(), "video/mp4")
    assert filename.endswith(".mp4")
    assert 2 <= len(frames) <= 3
    assert frames[0] != frames[-1]


def test_unrelated_or_sensitive_conversation_uses_golden_prompt(tmp_path):
    import asyncio
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from pai.conversation import prepare_context
    from pai.gifs import GifFeature
    from pai.model_router import ProviderRoute, Quota, Router
    from pai.reply_engine import ReplyEngine
    from pai.timeline import build_timeline_prompt

    arc, store, policy = _gif_context(tmp_path)
    now = datetime.now(UTC)
    source = MessageRecord(10, 1, 2, 3, "M", "in disbelief", now - timedelta(hours=1))
    arc.append(source)
    assert store.remember(source, "asset", "a" * 64, "Disbelief.")
    complete = AsyncMock(return_value="yeah")
    route = ProviderRoute("fixture", 3, True, Quota(25, 800, 8000, 180000), complete)
    feature = GifFeature(
        store,
        None,
        ReplyEngine(Router(arc, (route,)), conversation_engine="timeline-roles"),
    )
    for n, text in enumerate(
        ("what color is frost", "i am in disbelief. no jokes please"), 11
    ):
        request = MessageRecord(n, 1, 2, 4, "N", text, now)
        ctx = prepare_context(arc, policy, request, timeline=True)
        reply = asyncio.run(feature.respond(ctx, True))
        assert reply.text == "yeah" and reply.entry is None
        assert (
            complete.call_args.args[0]
            == build_timeline_prompt(ctx, native_roles=True).request
        )


def test_gif_policy_is_explicit_and_strict_json(tmp_path):
    import json

    from pai.policy import load_policy

    path = tmp_path / "policy.json"
    raw = {
        "admin_opt_in": True,
        "notice_version": "gif-test",
        "guild_id": 1,
        "channel_ids": [2],
        "consenting_member_ids": [3],
        "external_ai_opt_in": True,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert not load_policy(path).permits_gif(1, 2, 3)
    raw["gif_reuse_opt_in"] = True
    raw["gif_consenting_member_ids"] = [4]
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(path)
    raw["gif_consenting_member_ids"] = [3]
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert load_policy(path).permits_gif(1, 2, 3)


@pytest.mark.parametrize("text", ["", "the audacity"])
def test_gateway_delivers_verified_file_with_optional_text(tmp_path, text):
    import asyncio
    from unittest.mock import AsyncMock, Mock

    import discord

    from pai.discord_gateway import PaiDiscordClient
    from pai.gifs import GifReply

    arc, store, policy = _gif_context(tmp_path)
    now = datetime.now(UTC)
    origin = MessageRecord(10, 1, 2, 3, "M", "disbelief", now)
    current = MessageRecord(11, 1, 2, 4, "N", "<@42> again?", now)
    arc.append(origin)
    arc.append(current)
    assert store.remember(origin, "asset", "a" * 64, "disbelief")
    selected = store.entry(origin)
    member = Mock(id=4, bot=False)
    guild = Mock(id=1, me=object(), owner_id=3)
    guild.fetch_member = AsyncMock(return_value=member)
    channel = Mock(spec=discord.TextChannel, id=2, guild=guild)
    channel.permissions_for.return_value = discord.Permissions.all()
    channel.send = AsyncMock(return_value=Mock(id=41, created_at=now))
    discord_msg = Mock(
        id=11, guild=guild, channel=channel, author=member, content=current.text
    )
    client = PaiDiscordClient(policy, AsyncMock(), archive=arc, respond=AsyncMock())
    client.get_channel = Mock(return_value=channel)
    feature = Mock()
    feature.respond = AsyncMock(return_value=GifReply(text, selected))
    feature.attachment = AsyncMock(
        return_value=discord.File(BytesIO(fixture_gif()), filename="reaction.gif")
    )
    feature.valid.return_value = True
    feature.store = store
    client.gifs = feature
    asyncio.run(client._deliver_reply(discord_msg, True, None))
    args, kwargs = channel.send.call_args
    assert args == (text or None,)
    assert kwargs["reference"].message_id == current.message_id
    assert kwargs["allowed_mentions"].to_dict() == {"parse": []}
    assert kwargs["file"].filename == "reaction.gif"
    assert arc.get(41) is None
    assert not store.candidates(current, "disbelief")
