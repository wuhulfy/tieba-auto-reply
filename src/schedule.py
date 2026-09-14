from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

# China has used UTC+8 without daylight-saving changes since 1991.  A fixed
# offset also keeps local Windows runs independent of the optional tzdata wheel.
BEIJING = timezone(timedelta(hours=8), name="Asia/Shanghai")

SCHEDULE_GROUPS: dict[int, frozenset[str]] = {
    0: frozenset({"52 6 * * *", "37 12 * * *", "47 19 * * *"}),
    1: frozenset({"24 7 * * *", "13 13 * * *", "33 21 * * *"}),
    2: frozenset({"41 8 * * *", "6 15 * * *", "18 22 * * *"}),
}


def rotation_group(day: date) -> int:
    """Use an absolute day number so rotation stays continuous across months."""
    return day.toordinal() % 3


def is_active_schedule(schedule_expr: str, now: datetime | None = None) -> bool:
    if not schedule_expr:
        return True  # workflow_dispatch / local manual run
    current = now.astimezone(BEIJING) if now else datetime.now(BEIJING)
    if not 6 <= current.hour <= 23:
        return False
    return schedule_expr.strip() in SCHEDULE_GROUPS[rotation_group(current.date())]


def main() -> None:
    expression = os.getenv("SCHEDULE_EXPR", "").strip()
    now = datetime.now(BEIJING)
    print(f"active={'true' if is_active_schedule(expression, now) else 'false'}")
    print(f"rotation_group={rotation_group(now.date())}")


if __name__ == "__main__":
    main()
