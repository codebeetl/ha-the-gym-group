"""Shared entity wiring for The Gym Group integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class TheGymGroupDeviceMixin:
    """Provide the device_id/gym_name-based device_info shared by every entity."""

    def __init__(self, device_id: str, gym_name: str) -> None:
        """Store the identifiers used to build device_info."""
        self._device_id = device_id
        self._gym_name = gym_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking this entity to the gym device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._gym_name,
            manufacturer="The Gym Group",
            model="Unofficial integration",
        )
