"""Calendar platform for The Gym Group integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TheGymGroupActivityCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    activity_coordinator: TheGymGroupActivityCoordinator = entry_data["activity"]
    busyness_data = entry_data["busyness"].data or {}
    device_id = str(busyness_data.get("gymLocationId") or entry.entry_id)
    gym_name = busyness_data.get("gymLocationName", "The Gym Group")

    async_add_entities(
        [TheGymGroupCalendarEntity(activity_coordinator, entry, device_id, gym_name)]
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
    CoordinatorEntity[TheGymGroupActivityCoordinator], CalendarEntity
):
    """Calendar entity exposing gym visits and booked classes."""

    _attr_has_entity_name = True
    _attr_name = "Gym Calendar"
    _attr_icon = "mdi:calendar-account"

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialise the calendar entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._gym_name = gym_name
        self._attr_unique_id = f"{device_id}_calendar"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so the entity appears on the existing device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._gym_name,
            manufacturer="The Gym Group",
            model="Unofficial integration",
        )

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
