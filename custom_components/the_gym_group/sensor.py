"""Sensor platform for The Gym Group."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HISTORICAL_ATTR_LIMIT
from .coordinator import TheGymGroupDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: TheGymGroupDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        TheGymGroupBusynessSensor(coordinator, entry),
        TheGymGroupStatusSensor(coordinator, entry),
    ]
    async_add_entities(entities)


def _device_identifier(
    coordinator: TheGymGroupDataUpdateCoordinator, entry: ConfigEntry
) -> str:
    """Return a stable identifier for the gym device.

    Prefers the gymLocationId from the API; falls back to the config entry id so
    the identifier is never None even before the first successful refresh.
    """
    data = coordinator.data or {}
    return str(data.get("gymLocationId") or entry.entry_id)


class _TheGymGroupBaseSensor(
    CoordinatorEntity[TheGymGroupDataUpdateCoordinator], SensorEntity
):
    """Shared base for The Gym Group sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TheGymGroupDataUpdateCoordinator,
        config_entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self.config_entry: ConfigEntry = config_entry
        self._device_id = _device_identifier(coordinator, config_entry)
        self._attr_unique_id = f"{self._device_id}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the sensor."""
        data = self.coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=data.get("gymLocationName", "The Gym Group"),
            manufacturer="The Gym Group",
            model="Unofficial integration",
        )


class TheGymGroupBusynessSensor(_TheGymGroupBaseSensor):
    """Representation of The Gym Group busyness sensor."""

    _attr_icon = "mdi:weight-lifter"
    _attr_native_unit_of_measurement = "people"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "busyness"

    def __init__(
        self,
        coordinator: TheGymGroupDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the busyness sensor."""
        super().__init__(coordinator, config_entry, "busyness")

    @property
    def native_value(self) -> int | None:
        """Return the current number of people in the gym."""
        data = self.coordinator.data or {}
        return data.get("currentCapacity")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a bounded set of extra attributes.

        The full ``historical`` payload can be large; we keep only the most
        recent ``HISTORICAL_ATTR_LIMIT`` entries. The full payload remains
        available via the diagnostics handler.
        """
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
            "status": data.get("status"),
        }
        return {k: v for k, v in raw.items() if v is not None}


class TheGymGroupStatusSensor(_TheGymGroupBaseSensor):
    """Representation of The Gym Group status sensor (open/closed)."""

    _attr_icon = "mdi:door"
    _attr_translation_key = "status"

    def __init__(
        self,
        coordinator: TheGymGroupDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, config_entry, "status")

    @property
    def native_value(self) -> str | None:
        """Return the current gym open/closed status."""
        data = self.coordinator.data or {}
        return data.get("status")
