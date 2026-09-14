from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法识别布尔值: {value!r}")


def _as_int(
    name: str, default: int, minimum: int, maximum: int | None = None
) -> int:
    raw = os.getenv(name)
    value = default if raw is None or not raw.strip() else int(raw)
    if value < minimum:
        raise ValueError(f"{name} 必须大于等于 {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} 必须在 {minimum}..{maximum} 之间")
    return value


@dataclass(frozen=True)
class Config:
    bduss: str
    username: str
    user_id: str
    forum: str
    reply_content: str
    dry_run: bool
    max_replies: int
    scan_limit: int
    max_thread_age_hours: int
    delay_min: int
    delay_max: int
    state_file: Path

    @classmethod
    def from_env(cls) -> "Config":
        delay_min = _as_int("REPLY_DELAY_MIN", 5, 0, 120)
        delay_max = _as_int("REPLY_DELAY_MAX", 10, 0, 120)
        if delay_min > delay_max:
            raise ValueError("REPLY_DELAY_MIN 不能大于 REPLY_DELAY_MAX")

        config = cls(
            bduss=os.getenv("BDUSS", "").strip(),
            username=os.getenv("TIEBA_USERNAME", "").strip(),
            user_id=os.getenv("TIEBA_USER_ID", "").strip(),
            forum=os.getenv("TIEBA_FORUM", "hifi交易").strip(),
            reply_content=os.getenv("REPLY_CONTENT", "bd").strip(),
            dry_run=_as_bool(os.getenv("DRY_RUN"), True),
            max_replies=_as_int("MAX_REPLIES", 20, 1),
            scan_limit=_as_int("THREAD_SCAN_LIMIT", 100, 20, 300),
            max_thread_age_hours=_as_int("MAX_THREAD_AGE_HOURS", 6, 1, 48),
            delay_min=delay_min,
            delay_max=delay_max,
            state_file=Path(os.getenv("STATE_FILE", ".state/processed.json")),
        )
        if not config.bduss:
            raise ValueError("缺少 BDUSS")
        if not config.forum:
            raise ValueError("TIEBA_FORUM 不能为空")
        if not config.reply_content:
            raise ValueError("REPLY_CONTENT 不能为空")
        if not config.username:
            raise ValueError("必须设置 TIEBA_USERNAME（帖子中的精确显示昵称）以便去重")
        if config.user_id and not config.user_id.isdigit():
            raise ValueError("TIEBA_USER_ID 必须是纯数字")
        return config
