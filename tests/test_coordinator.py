"""Tests for coordinator helper functions."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from custom_components.the_gym_group.coordinator import _parse_checkin_dt


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
