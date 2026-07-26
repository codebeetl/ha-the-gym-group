"""Tests for coordinator helper functions."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from custom_components.the_gym_group.coordinator import _add_duration, _parse_checkin_dt


def test_parse_checkin_dt_attaches_tz_to_naive_timestamp() -> None:
    """A naive checkInDate gets the given timezone attached."""
    raw = {"checkInDate": "2025-04-01T09:00:00", "timezone": "Europe/London"}
    result = _parse_checkin_dt(raw)
    assert result == datetime(2025, 4, 1, 9, 0, 0, tzinfo=ZoneInfo("Europe/London"))


def test_parse_checkin_dt_preserves_offset_aware_instant() -> None:
    """An already-aware checkInDate keeps its real instant, not just its wall clock."""
    raw = {"checkInDate": "2025-07-01T09:00:00+00:00", "timezone": "Europe/London"}
    result = _parse_checkin_dt(raw)
    assert result == datetime(2025, 7, 1, 9, 0, 0, tzinfo=timezone.utc)


def test_add_duration_uses_real_elapsed_time_across_dst_fallback() -> None:
    """A check-in spanning the UK's autumn DST fallback ends at the right instant."""
    # 2025-10-26 is the UK's fallback date: clocks go from BST (+01:00) back to GMT.
    start_dt = datetime(2025, 10, 26, 0, 30, tzinfo=ZoneInfo("Europe/London"))
    end_dt = _add_duration(start_dt, duration_ms=7_200_000)  # +2h of real elapsed time
    assert end_dt.astimezone(timezone.utc) == datetime(
        2025, 10, 26, 1, 30, tzinfo=timezone.utc
    )
    # Naive wall-clock addition would have wrongly landed on 02:30 local.
    assert end_dt != start_dt + timedelta(hours=2)
