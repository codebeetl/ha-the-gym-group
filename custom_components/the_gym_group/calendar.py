"""Calendar platform for The Gym Group integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TheGymGroupConfigEntry
from .coordinator import TheGymGroupActivityCoordinator
from .entity import TheGymGroupDeviceMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TheGymGroupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the calendar platform."""
    runtime_data = entry.runtime_data
    activity_coordinator = runtime_data.activity
    busyness_data = runtime_data.busyness.data or {}
    # Scoped by entry_id (not just gymLocationId) so two accounts sharing the
    # same home gym don't collide on unique_id / device identifiers.
    device_id = entry.entry_id
    gym_name = busyness_data.get("gymLocationName", "The Gym Group")

    async_add_entities(
        [TheGymGroupCalendarEntity(activity_coordinator, device_id, gym_name)]
    )


def _make_visit_event(checkin: dict[str, Any]) -> CalendarEvent:
    """Build a CalendarEvent from a parsed check-in dict."""
    start: datetime = checkin["start"]
    end: datetime = checkin["end"] or start + timedelta(hours=1)
    return CalendarEvent(
        start=start,
        end=end,
        summary="Gym Visit",
        location=checkin.get("gym_name"),
        uid=f"visit_{start.isoformat()}",
    )


def _make_class_event(cls: dict[str, Any], gym_name: str) -> CalendarEvent:
    """Build a CalendarEvent from a parsed booked-class dict."""
    start: datetime = cls["start"]
    end: datetime = cls["end"] or start + timedelta(hours=1)
    instructor: str = cls.get("instructor", "")
    return CalendarEvent(
        start=start,
        end=end,
        summary=cls.get("name") or "Booked Class",
        description=instructor or None,
        location=gym_name,
        uid=f"class_{start.isoformat()}",
    )


class TheGymGroupCalendarEntity(
    TheGymGroupDeviceMixin, CoordinatorEntity[TheGymGroupActivityCoordinator], CalendarEntity
):
    """Calendar entity exposing gym visits and booked classes."""

    _attr_has_entity_name = True
    _attr_name = "Gym Calendar"
    _attr_icon = "mdi:calendar-account"

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialise the calendar entity."""
        CoordinatorEntity.__init__(self, coordinator)
        TheGymGroupDeviceMixin.__init__(self, device_id, gym_name)
        self._attr_unique_id = f"{device_id}_calendar"

    def _all_events(self) -> list[CalendarEvent]:
        """Return all known events sorted chronologically."""
        data = self.coordinator.data or {}
        events: list[CalendarEvent] = [
            _make_visit_event(ci) for ci in data.get("calendar_checkins", [])
        ] + [
            _make_class_event(cls, self._gym_name)
            for cls in data.get("calendar_classes", [])
        ]
        events.sort(key=lambda e: e.start)
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the currently active event, or the next upcoming one."""
        now = datetime.now(timezone.utc)
        next_upcoming: CalendarEvent | None = None
        for ev in self._all_events():
            if ev.start <= now <= ev.end:
                return ev
            if ev.start > now and next_upcoming is None:
                next_upcoming = ev
        return next_upcoming

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events overlapping the requested date range."""
        return [
            ev
            for ev in self._all_events()
            if ev.start < end_date and ev.end > start_date
        ]
