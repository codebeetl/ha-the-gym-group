"""Tests for coordinator helper functions."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from custom_components.the_gym_group.coordinator import (
    _add_duration,
    _find_next_class,
    _parse_booked_class,
    _parse_checkin_dt,
    _summarize_checkins,
)


def test_parse_checkin_dt_treats_naive_timestamp_as_utc() -> None:
    """A naive checkInDate is the API's own UTC clock, not local wall time.

    Attaching the check-in's ``timezone`` field directly to the naive string
    (as if it were already local wall time) shifts the real instant by that
    zone's UTC offset - during BST that reported every visit an hour early.
    """
    raw = {"checkInDate": "2025-07-01T09:00:00", "timezone": "Europe/London"}
    result = _parse_checkin_dt(raw)
    assert result == datetime(2025, 7, 1, 9, 0, 0, tzinfo=timezone.utc)
    assert result.utcoffset() == timedelta(hours=1)  # BST wall clock is 10:00


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


def test_find_next_class_excludes_already_started_classes() -> None:
    """An in-progress class must not be reported as the next class."""
    now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    in_progress = {
        "brief": {
            "name": "In Progress Class",
            "startDateTime": int((now - timedelta(minutes=10)).timestamp() * 1000),
            "endDateTime": int((now + timedelta(minutes=20)).timestamp() * 1000),
            "cancelled": False,
        }
    }
    upcoming = {
        "brief": {
            "name": "Upcoming Class",
            "startDateTime": int((now + timedelta(hours=1)).timestamp() * 1000),
            "endDateTime": int((now + timedelta(hours=2)).timestamp() * 1000),
            "cancelled": False,
        }
    }
    result = _find_next_class([in_progress, upcoming], now)
    assert result is not None
    assert result["name"] == "Upcoming Class"


def test_parse_booked_class_returns_none_for_cancelled_class() -> None:
    """A cancelled class must not be normalized."""
    item = {"brief": {"name": "Cancelled", "startDateTime": 1_000, "cancelled": True}}
    assert _parse_booked_class(item) is None


def test_parse_booked_class_returns_none_without_a_start_time() -> None:
    """A class with no startDateTime must not be normalized."""
    item = {"brief": {"name": "No Start", "startDateTime": 0, "cancelled": False}}
    assert _parse_booked_class(item) is None


def test_parse_booked_class_normalizes_fields() -> None:
    """Duration, spots, and defaults are computed from the raw brief."""
    item = {
        "brief": {
            "name": "Spin",
            "startDateTime": 1_000,
            "endDateTime": 1_000 + 30 * 60_000,
            "instructor": {"fullName": "Jane Smith"},
            "maxCapacity": 20,
            "totalBooked": 15,
            "cancelled": False,
        }
    }
    result = _parse_booked_class(item)
    assert result is not None
    assert result["name"] == "Spin"
    assert result["instructor"] == "Jane Smith"
    assert result["available_spots"] == 5
    assert result["duration_minutes"] == 30
    assert result["end_dt"] is not None


def test_summarize_checkins_picks_latest_by_real_instant_not_lexical_string() -> None:
    """Mixed naive/offset-aware checkInDate strings must not be compared lexically.

    "2025-07-01T10:00:00" (naive, treated as 10:00 UTC) sorts lexically
    *before* "2025-07-01T14:00:00+05:00" (which is actually only 09:00 UTC)
    even though the naive one is an hour later in real time.
    """
    later_but_lexically_smaller = {
        "checkInDate": "2025-07-01T10:00:00",
        "timezone": "Europe/London",
        "gymLocationName": "Later Gym",
        "duration": 1_800_000,
    }
    earlier_but_lexically_larger = {
        "checkInDate": "2025-07-01T14:00:00+05:00",
        "timezone": "Europe/London",
        "gymLocationName": "Earlier Gym",
        "duration": 1_800_000,
    }
    now = datetime(2025, 7, 1, 12, 0, tzinfo=timezone.utc)

    result = _summarize_checkins(
        [earlier_but_lexically_larger, later_but_lexically_smaller], now
    )

    assert result["latest_checkin_gym"] == "Later Gym"


def test_summarize_checkins_monthly_and_recent_use_real_instants() -> None:
    """Monthly/recent filters must not misclassify a mixed-format check-in."""
    now = datetime(2025, 7, 15, 12, 0, tzinfo=timezone.utc)
    # 2025-06-30T23:30:00+00:00 is the last instant of June - must NOT count
    # towards July's monthly stats even though its string sorts after
    # "2025-07-01..." would if the offset were stripped.
    last_of_june = {
        "checkInDate": "2025-06-30T23:30:00+00:00",
        "timezone": "UTC",
        "duration": 3_600_000,
    }
    first_of_july = {
        "checkInDate": "2025-07-01T00:30:00+00:00",
        "timezone": "UTC",
        "duration": 3_600_000,
    }

    result = _summarize_checkins([last_of_june, first_of_july], now)

    assert result["monthly_visits"] == 1
    assert result["monthly_hours"] == 1.0
