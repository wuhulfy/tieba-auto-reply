from datetime import date, datetime
from src.schedule import BEIJING, SCHEDULE_GROUPS, is_active_schedule, rotation_group


def test_rotation_is_continuous_across_month_boundary() -> None:
    first = date(2026, 8, 31)
    second = date(2026, 9, 1)
    assert rotation_group(second) == (rotation_group(first) + 1) % 3


def test_only_current_group_is_active() -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=BEIJING)
    group = rotation_group(now.date())
    active_expr = next(iter(SCHEDULE_GROUPS[group]))
    inactive_expr = next(iter(SCHEDULE_GROUPS[(group + 1) % 3]))
    assert is_active_schedule(active_expr, now)
    assert not is_active_schedule(inactive_expr, now)


def test_manual_run_is_active_inside_window() -> None:
    now = datetime(2026, 9, 14, 12, 0, tzinfo=BEIJING)
    assert is_active_schedule("", now)


def test_scheduled_run_outside_window_is_inactive() -> None:
    now = datetime(2026, 9, 14, 0, 30, tzinfo=BEIJING)
    group = rotation_group(now.date())
    active_expr = next(iter(SCHEDULE_GROUPS[group]))
    assert not is_active_schedule(active_expr, now)
