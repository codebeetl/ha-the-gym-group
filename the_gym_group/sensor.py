"""Sensor platform for The Gym Group."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TheGymGroupDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: TheGymGroupDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [TheGymGroupBusynessSensor(coordinator, entry)]
    async_add_entities(entities)


class TheGymGroupBusynessSensor(
    CoordinatorEntity[TheGymGroupDataUpdateCoordinator], SensorEntity
):
    """Representation of a The Gym Group Busyness Sensor."""

    _attr_icon = "mdi:weight-lifter"
    _attr_native_unit_of_measurement = "people"
    _attr_has_entity_name = True
    _attr_name = "Gym Population"

    def __init__(
        self, coordinator: TheGymGroupDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry: ConfigEntry = config_entry
        self._attr_unique_id = (
            f"{coordinator.data.get('gymLocationId', config_entry.entry_id)}_busyness"
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor (current capacity)."""
        return self.coordinator.data.get("currentCapacity")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details from the API as attributes."""
        data: dict[str, Any] = self.coordinator.data
        if not data:
            return {}

        return {
            "gym_location_id": data.get("gymLocationId"),
            "gym_location_name": data.get("gymLocationName"),
            "current_percentage": data.get("currentPercentage"),
            "historical": data.get("historical"),
            "status": data.get("status"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the sensor."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.data.get(
                        "gymLocationId", self.config_entry.entry_id
                    ),
                )
            },
            name=self.coordinator.data.get("gymLocationName", "The Gym Group"),
            manufacturer="The Gym Group",
            model="Unofficial integration",
        )

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:weight-lifter"


class TheGymGroupStatusSensor(
    CoordinatorEntity[TheGymGroupDataUpdateCoordinator], SensorEntity
):
    """Representation of a The Gym Group Status Sensor."""

    _attr_icon = "mdi:door"
    _attr_has_entity_name = True
    _attr_translation_key = "status"

    def __init__(
        self, coordinator: TheGymGroupDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry: ConfigEntry = config_entry
        self._attr_unique_id = (
            f"{coordinator.data.get('gymLocationId', config_entry.entry_id)}_status"
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor (current status)."""
        return self.coordinator.data.get("status")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to link to the same device."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.data.get(
                        "gymLocationId", self.config_entry.entry_id
                    ),
                )
            }
        )
