"""Freeze the owner-approved P9.11 conversational inputs and router."""

from hashlib import sha256
from pathlib import Path

import pytest

_BASELINE = {
    "uv.lock": "505a3db56a87ad4dfd63b4a62d0d2ca76cf8400c95bc36c0477fdb98286476ee",
    "src/pai/timeline.py": "91b3024a710a036f8cf91e3c60b2cd3c835221a4dfc449f652e7b9e050cdc162",
    "src/pai/providers.py": "ed64c0453bfee8102c51d839b8dcc93d055f83faeed64a4a92a715e2fc5ee910",
    "src/pai/conversation.py": "0658c53f3af801cbd1ddbe99f2aa84d7d92754ae2d7dee63a869e54e6e6a2a35",
    "src/pai/reply_engine.py": "f61a60c2b7beef996631d77c705e29636e07771c873c36afaccaa3a05eea7069",
    "src/pai/prompts.py": "16b55eaf76765a3d141d48c3dff92ef5a0a4ddbb2d317e60c04d6703a78ac314",
    "src/pai/voice.py": "ec13cecb84af8b972ea28e605410ddfc509098bfb1b9750215f5d14bbd4e1c07",
}


@pytest.mark.parametrize(("name", "expected"), _BASELINE.items())
def test_p911_golden_behavior_sources(name, expected):
    path = Path(__file__).resolve().parent.parent / name
    normalized = path.read_text(encoding="utf-8").encode("utf-8")
    assert sha256(normalized).hexdigest() == expected, (
        "P9.11 owner-approved behavior changed. A narrowly scoped change requires "
        "explicit owner approval and a documented baseline update."
    )
