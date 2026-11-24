"""Resolve only animated media present in an authorized Discord message."""

import json
import os
import re
import shutil
import subprocess
from fractions import Fraction
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from PIL import Image

from pai.media import MAX_DOWNLOAD_BYTES, MediaError, allowed_url, decode_frames

MIMES = frozenset({"image/gif", "image/apng", "image/png", "image/webp", "video/mp4"})
_LINK = re.compile(r"https://[^\s<>]+", re.IGNORECASE)
_ANIMATED_SUFFIXES = frozenset({".gif", ".apng", ".webp"})
_MAX_ASSETS = 3
_VIDEO_SIZE = 256
_VIDEO_FRAME_BYTES = _VIDEO_SIZE * _VIDEO_SIZE * 3


class GifAsset:
    def __init__(self, url: str) -> None:
        self.url = url
        parts = urlsplit(url)
        self.identity = sha256(f"{parts.hostname}{parts.path}".encode()).hexdigest()


def linked_gif_page(text: str) -> bool:
    for match in _LINK.finditer(text):
        parsed = _parts(match[0].rstrip(".,)>"))
        if parsed is not None and (
            (
                parsed.hostname in {"tenor.com", "www.tenor.com"}
                and parsed.path.startswith("/view/")
            )
            or (
                parsed.hostname in {"giphy.com", "www.giphy.com"}
                and parsed.path.startswith("/gifs/")
            )
        ):
            return True
    return False


def _parts(url: str):
    try:
        return urlsplit(url)
    except ValueError:
        return None


def discover_gifs(message) -> tuple[GifAsset, ...]:
    """A page link is a hint to refresh Discord metadata, never a fetch target."""
    found = {}

    def add(url):
        if url and allowed_url(url):
            item = GifAsset(url)
            found.setdefault(item.identity, item)

    for file in message.attachments:
        path = PurePosixPath(file.filename.lower())
        if file.size <= MAX_DOWNLOAD_BYTES and (
            path.suffix in _ANIMATED_SUFFIXES
            or file.content_type == "image/apng"
            or file.filename.lower().endswith(".gif.mp4")
        ):
            add(file.url)
    for embed in message.embeds:
        for field in (embed.image, embed.video, embed.thumbnail):
            for url in (field.url, getattr(field, "proxy_url", None)):
                if not url:
                    continue
                parsed = _parts(url)
                if parsed is None:
                    continue
                suffix = PurePosixPath(parsed.path.lower()).suffix
                if suffix in _ANIMATED_SUFFIXES or (
                    embed.type == "gifv" and suffix == ".mp4"
                ):
                    add(url)
    for match in _LINK.finditer(message.content):
        url = match[0].rstrip(".,)>")
        parsed = _parts(url)
        if parsed is None:
            continue
        suffix = PurePosixPath(parsed.path.lower()).suffix
        if suffix in _ANIMATED_SUFFIXES or (
            suffix == ".mp4"
            and parsed.hostname not in {"cdn.discordapp.com", "media.discordapp.net"}
        ):
            add(url)
    return tuple(found.values())[:_MAX_ASSETS]


def decode_animation(data: bytes, mime: str) -> tuple[tuple[bytes, ...], str]:
    if not data or len(data) > MAX_DOWNLOAD_BYTES or mime not in MIMES:
        raise MediaError("Animation exceeds the byte limit or type is unsupported")
    if mime == "video/mp4":
        return _decode_mp4(data), "reaction.mp4"
    try:
        with Image.open(BytesIO(data), formats=("GIF", "PNG", "WEBP")) as image:
            if not getattr(image, "is_animated", False):
                raise MediaError("The source image is not animated")
            suffix = {"GIF": "gif", "PNG": "png", "WEBP": "webp"}[image.format]
    except (KeyError, OSError, ValueError, Image.DecompressionBombError, SyntaxError):
        raise MediaError("Invalid animated image") from None
    frames = decode_frames(data)
    if len(frames) < 2:
        raise MediaError("Animation does not yield distinguishable sampled frames")
    return frames, f"reaction.{suffix}"


def _decode_mp4(data: bytes) -> tuple[bytes, ...]:
    ffmpeg = shutil.which("ffmpeg")
    probe = shutil.which("ffprobe")
    if not ffmpeg or not probe or data[4:8] != b"ftyp":
        raise MediaError("A supported local decoder and MP4 container are required")
    try:
        with TemporaryDirectory(prefix="pai-gif-") as folder:
            filename = Path(folder, "input.mp4")
            filename.write_bytes(data)
            input_options = [
                "-v",
                "error",
                "-max_alloc",
                "25165824",
                "-protocol_whitelist",
                "file,pipe",
                "-f",
                "mov",
                "-enable_drefs",
                "0",
                "-use_absolute_path",
                "0",
            ]
            options = dict(
                stdin=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                timeout=4,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            metadata = subprocess.run(
                [
                    probe,
                    *input_options,
                    "-show_entries",
                    "stream=codec_type,width,height,avg_frame_rate,duration",
                    "-of",
                    "json",
                    str(filename),
                ],
                **options,
            )
            (stream,) = json.loads(metadata.stdout)["streams"]
            width, height = int(stream["width"]), int(stream["height"])
            fps = float(Fraction(stream["avg_frame_rate"]))
            duration = float(stream["duration"])
            if not (
                stream["codec_type"] == "video"
                and 0 < width * height <= 1_100_000
                and 0 < fps <= 60
                and 0.12 <= duration <= 8
                and width * height * duration * fps <= 120_000_000
            ):
                raise MediaError(
                    "Video exceeds the animation dimensions, time or frame-rate limit"
                )
            frames = subprocess.run(
                [
                    ffmpeg,
                    *input_options,
                    "-nostdin",
                    "-threads",
                    "1",
                    "-noautorotate",
                    "-i",
                    str(filename),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-sn",
                    "-dn",
                    "-filter_threads",
                    "1",
                    "-vf",
                    f"fps={max(2, min(20, 3 / duration))},scale=256:256:force_original_aspect_ratio=decrease,"
                    "pad=256:256:(ow-iw)/2:(oh-ih)/2",
                    "-frames:v",
                    "16",
                    "-threads",
                    "1",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "pipe:1",
                ],
                **options,
            ).stdout
    except (
        subprocess.SubprocessError,
        OSError,
        TypeError,
        KeyError,
        ValueError,
        ZeroDivisionError,
    ):
        raise MediaError("Unable to decode a bounded embedded video") from None
    count, tail = divmod(len(frames), _VIDEO_FRAME_BYTES)
    if tail or not 2 <= count <= 16:
        raise MediaError("Video did not produce an ordered animation sample")
    sampled = []
    for i in sorted({0, count // 2, count - 1}):
        offset = i * _VIDEO_FRAME_BYTES
        image = Image.frombytes(
            "RGB",
            (_VIDEO_SIZE, _VIDEO_SIZE),
            frames[offset : offset + _VIDEO_FRAME_BYTES],
        )
        out = BytesIO()
        image.save(out, "PNG")
        if not sampled or out.getvalue() != sampled[-1]:
            sampled.append(out.getvalue())
    if len(sampled) < 2:
        raise MediaError("Video sample did not show motion")
    return tuple(sampled)
