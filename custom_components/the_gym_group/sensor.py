"""Sensor platform for The Gym Group."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    BUSYNESS_TRANSLATION_KEY,
    DOMAIN,
    HISTORICAL_ATTR_LIMIT,
    LAST_CHECKIN_TRANSLATION_KEY,
    MONTHLY_TIME_TRANSLATION_KEY,
    MONTHLY_VISITS_TRANSLATION_KEY,
    NEXT_CLASS_TRANSLATION_KEY,
    STATUS_TRANSLATION_KEY,
)
from .coordinator import TheGymGroupActivityCoordinator, TheGymGroupDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    busyness_coordinator: TheGymGroupDataUpdateCoordinator = entry_data["busyness"]
    activity_coordinator: TheGymGroupActivityCoordinator = entry_data["activity"]

    # Resolve device identity once from the busyness coordinator (already refreshed).
    busyness_data = busyness_coordinator.data or {}
    device_id = str(busyness_data.get("gymLocationId") or entry.entry_id)
    gym_name = busyness_data.get("gymLocationName", "The Gym Group")

    async_add_entities(
        [
            TheGymGroupBusynessSensor(busyness_coordinator, entry, device_id, gym_name),
            TheGymGroupStatusSensor(busyness_coordinator, entry, device_id, gym_name),
            TheGymGroupLastCheckinSensor(
                activity_coordinator, entry, device_id, gym_name
            ),
            TheGymGroupMonthlyVisitsSensor(
                activity_coordinator, entry, device_id, gym_name
            ),
            TheGymGroupMonthlyTimeSensor(
                activity_coordinator, entry, device_id, gym_name
            ),
            TheGymGroupNextClassSensor(
                activity_coordinator, entry, device_id, gym_name
            ),
        ]
    )


class _TheGymGroupBaseSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity
):
    """Shared base for The Gym Group sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        config_entry: ConfigEntry,
        unique_suffix: str,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self.config_entry: ConfigEntry = config_entry
        self._device_id = device_id
        self._gym_name = gym_name
        self._attr_unique_id = f"{device_id}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._gym_name,
            manufacturer="The Gym Group",
            model="Unofficial integration",
        )


class TheGymGroupBusynessSensor(_TheGymGroupBaseSensor):
    """Representation of The Gym Group busyness sensor."""

    _attr_icon = "mdi:weight-lifter"
    _attr_native_unit_of_measurement = "people"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = BUSYNESS_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the busyness sensor."""
        super().__init__(coordinator, config_entry, "busyness", device_id, gym_name)

    @property
    def native_value(self) -> int | None:
        """Return the current number of people in the gym."""
        data = self.coordinator.data or {}
        return data.get("currentCapacity")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a bounded set of extra attributes."""
        data = self.coordinator.data
        if not data:
            return {}

        historical = data.get("historical")
        if isinstance(historical, list):
            historical = historical[-HISTORICAL_ATTR_LIMIT:]

        raw = {
            "gym_location_id": data.get("gymLocationId"),
            "gym_location_name": data.get("gymLocationName"),
            "current_percentage": data.get("currentPercentage"),
            "historical": historical,
        }
        return {k: v for k, v in raw.items() if v is not None}


class TheGymGroupStatusSensor(_TheGymGroupBaseSensor):
    """Representation of The Gym Group status sensor (open/closed)."""

    _attr_icon = "mdi:door"
    _attr_translation_key = STATUS_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, config_entry, "status", device_id, gym_name)

    @property
    def native_value(self) -> str | None:
        """Return the current gym open/closed status."""
        data = self.coordinator.data or {}
        return data.get("status")


class TheGymGroupLastCheckinSensor(_TheGymGroupBaseSensor):
    """Timestamp of the user's most recent gym check-in."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:login"
    _attr_translation_key = LAST_CHECKIN_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the last check-in sensor."""
        super().__init__(coordinator, config_entry, "last_checkin", device_id, gym_name)

    @property
    def native_value(self) -> datetime | None:
        """Return the datetime of the last check-in."""
        data = self.coordinator.data or {}
        return data.get("latest_checkin")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return gym name and visit duration for the last check-in."""
        data = self.coordinator.data or {}
        raw = {
            "gym_location_name": data.get("latest_checkin_gym"),
            "duration_minutes": data.get("latest_checkin_duration_minutes"),
        }
        return {k: v for k, v in raw.items() if v is not None}


class TheGymGroupMonthlyVisitsSensor(_TheGymGroupBaseSensor):
    """Number of check-ins this calendar month."""

    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "visits"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = MONTHLY_VISITS_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the monthly visits sensor."""
        super().__init__(
            coordinator, config_entry, "monthly_visits", device_id, gym_name
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of check-ins this month."""
        data = self.coordinator.data or {}
        return data.get("monthly_visits")


class TheGymGroupMonthlyTimeSensor(_TheGymGroupBaseSensor):
    """Total gym time this calendar month in hours."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_translation_key = MONTHLY_TIME_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the monthly gym time sensor."""
        super().__init__(
            coordinator, config_entry, "monthly_time", device_id, gym_name
        )

    @property
    def native_value(self) -> float | None:
        """Return total hours spent in the gym this month."""
        data = self.coordinator.data or {}
        return data.get("monthly_hours")


class TheGymGroupNextClassSensor(_TheGymGroupBaseSensor):
    """Timestamp of the user's next booked class."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = NEXT_CLASS_TRANSLATION_KEY

    def __init__(
        self,
        coordinator: TheGymGroupActivityCoordinator,
        config_entry: ConfigEntry,
        device_id: str,
        gym_name: str,
    ) -> None:
        """Initialize the next class sensor."""
        super().__init__(coordinator, config_entry, "next_class", device_id, gym_name)

    @property
    def native_value(self) -> datetime | None:
        """Return the start time of the next booked class."""
        data = self.coordinator.data or {}
        next_class = data.get("next_class")
        if next_class is None:
            return None
        return next_class.get("start_dt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return class name, instructor, available spots, and duration."""
        data = self.coordinator.data or {}
        next_class = data.get("next_class")
        if not next_class:
            return {}
        raw = {
            "class_name": next_class.get("name"),
            "instructor": next_class.get("instructor") or None,
            "available_spots": next_class.get("available_spots"),
            "duration_minutes": next_class.get("duration_minutes"),
        }
        return {k: v for k, v in raw.items() if v is not None}
