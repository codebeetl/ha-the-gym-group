"""Diagnostics support for The Gym Group."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# entry_id, created_at and modified_at are redacted because they are
# non-deterministic and would make snapshot tests unreliable.
TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "entry_id", "created_at", "modified_at"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "busyness_data": entry_data["busyness"].data or {},
        "activity_data": entry_data["activity"].data or {},
    }
