"""Tests for the calendar platform."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from custom_components.the_gym_group.calendar import (
    TheGymGroupCalendarEntity,
    _make_class_event,
    _make_visit_event,
)


def _make_entity(data: dict) -> TheGymGroupCalendarEntity:
    coordinator = MagicMock()
    coordinator.data = data
    return TheGymGroupCalendarEntity(coordinator, "entry-id", "Test Gym")


def test_make_visit_event_falls_back_to_one_hour_when_end_missing() -> None:
    """A check-in with no known end time defaults to a 1-hour block."""
    start = datetime(2025, 6, 1, 9, 0, tzinfo=timezone.utc)
    event = _make_visit_event({"start": start, "end": None, "gym_name": "Test Gym"})
    assert event.end == start + timedelta(hours=1)
    assert event.location == "Test Gym"
    assert event.summary == "Gym Visit"
    assert event.uid == f"visit_{start.isoformat()}"


def test_make_class_event_defaults_name_and_instructor() -> None:
    """A class with no name/instructor uses sensible defaults."""
    start = datetime(2025, 6, 1, 9, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)
    event = _make_class_event(
        {"start": start, "end": end, "name": "", "instructor": ""}, "Test Gym"
    )
    assert event.summary == "Booked Class"
    assert event.description is None
    assert event.location == "Test Gym"
    assert event.uid == f"class_{start.isoformat()}"


def test_event_returns_currently_active_event() -> None:
    """An event spanning "now" is returned even if a later one exists too."""
    now = datetime.now(timezone.utc)
    active_checkin = {
        "start": now - timedelta(minutes=10),
        "end": now + timedelta(minutes=10),
        "gym_name": "Test Gym",
    }
    future_class = {
        "start": now + timedelta(hours=1),
        "end": now + timedelta(hours=2),
        "name": "Spin",
        "instructor": "",
    }
    entity = _make_entity(
        {"calendar_checkins": [active_checkin], "calendar_classes": [future_class]}
    )
    assert entity.event is not None
    assert entity.event.summary == "Gym Visit"


def test_event_returns_next_upcoming_when_none_active() -> None:
    """With nothing active, the soonest upcoming event is returned."""
    now = datetime.now(timezone.utc)
    soon_class = {
        "start": now + timedelta(minutes=30),
        "end": now + timedelta(minutes=45),
        "name": "Spin",
        "instructor": "",
    }
    later_class = {
        "start": now + timedelta(hours=2),
        "end": now + timedelta(hours=3),
        "name": "Yoga",
        "instructor": "",
    }
    entity = _make_entity(
        {"calendar_checkins": [], "calendar_classes": [later_class, soon_class]}
    )
    assert entity.event is not None
    assert entity.event.summary == "Spin"


def test_event_returns_none_when_no_events() -> None:
    """No known events means no active/next event."""
    entity = _make_entity({"calendar_checkins": [], "calendar_classes": []})
    assert entity.event is None


async def test_async_get_events_filters_by_range_overlap() -> None:
    """Only events overlapping the requested window are returned."""
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    inside = {
        "start": base + timedelta(days=1),
        "end": base + timedelta(days=1, hours=1),
        "gym_name": "Test Gym",
    }
    outside = {
        "start": base + timedelta(days=10),
        "end": base + timedelta(days=10, hours=1),
        "gym_name": "Test Gym",
    }
    entity = _make_entity({"calendar_checkins": [inside, outside], "calendar_classes": []})

    events = await entity.async_get_events(
        hass=MagicMock(),
        start_date=base,
        end_date=base + timedelta(days=2),
    )

    assert len(events) == 1
    assert events[0].start == inside["start"]
