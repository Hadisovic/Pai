"""Local, operator-provisioned Discord collection scope."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrivacyPolicy:
    admin_opt_in: bool = False
    notice_version: str = ""
    guild_id: int | None = None
    channel_ids: frozenset[int] = frozenset()
    consenting_member_ids: frozenset[int] = frozenset()
    retention_days: int = 30
    external_ai_opt_in: bool = False
    media_opt_in: bool = False

    @property
    def is_enabled(self) -> bool:
        return (
            self.admin_opt_in
            and bool(self.notice_version.strip())
            and self.guild_id is not None
            and bool(self.channel_ids)
            and bool(self.consenting_member_ids)
        )

    def permits_channel(self, guild_id: int, channel_id: int) -> bool:
        return (
            self.is_enabled
            and guild_id == self.guild_id
            and channel_id in self.channel_ids
        )

    def permits(self, guild_id: int, channel_id: int, author_id: int) -> bool:
        return (
            self.permits_channel(guild_id, channel_id)
            and author_id in self.consenting_member_ids
        )


def _snowflake(value: object) -> bool:
    return type(value) is int and 0 < value < 2**64


def _snowflakes(config: dict, field: str) -> frozenset[int]:
    values = config.get(field, [])
    if not isinstance(values, list) or not all(_snowflake(value) for value in values):
        raise ValueError(f"{field} must be a list of positive Discord IDs")
    return frozenset(values)


def load_policy(path: Path) -> PrivacyPolicy:
    try:
        source = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PrivacyPolicy()
    try:
        config = json.loads(source)
    except (ValueError, RecursionError) as error:
        raise ValueError("Invalid policy JSON") from error
    if (
        not isinstance(config, dict)
        or config.keys() - PrivacyPolicy.__dataclass_fields__.keys()
    ):
        raise ValueError("Invalid policy fields")
    guild_id = config.get("guild_id")
    if guild_id is not None and not _snowflake(guild_id):
        raise ValueError("guild_id must be a positive Discord ID")
    admin_opt_in = config.get("admin_opt_in", False)
    notice_version = config.get("notice_version", "")
    if type(admin_opt_in) is not bool or not isinstance(notice_version, str):
        raise ValueError("Invalid admin_opt_in or notice_version")
    retention_days = config.get("retention_days", 30)
    if type(retention_days) is not int or not 1 <= retention_days <= 365:
        raise ValueError("retention_days must be an integer between 1 and 365")
    external_ai_opt_in = config.get("external_ai_opt_in", False)
    if type(external_ai_opt_in) is not bool:
        raise ValueError("external_ai_opt_in must be a boolean")
    media_opt_in = config.get("media_opt_in", False)
    if type(media_opt_in) is not bool:
        raise ValueError("media_opt_in must be a boolean")
    return PrivacyPolicy(
        admin_opt_in=admin_opt_in,
        notice_version=notice_version,
        guild_id=guild_id,
        channel_ids=_snowflakes(config, "channel_ids"),
        consenting_member_ids=_snowflakes(config, "consenting_member_ids"),
        retention_days=retention_days,
        external_ai_opt_in=external_ai_opt_in,
        media_opt_in=media_opt_in,
    )
