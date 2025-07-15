"""Diagnostics support for The Gym Group."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TheGymGroupDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TheGymGroupDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Redact sensitive information from the config entry data
    redacted_config: dict[str, Any] = dict(entry.data)
    redacted_config.pop("password", None)

    return {
        "config_entry": redacted_config,
        "coordinator_data": coordinator.data,
    }
