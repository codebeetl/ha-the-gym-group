"""Diagnostics support for The Gym Group."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import TheGymGroupConfigEntry

# entry_id, created_at and modified_at are redacted because they are
# non-deterministic and would make snapshot tests unreliable. unique_id (the
# Netpulse account UUID) is redacted because it's a stable personal identifier.
TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "entry_id",
    "created_at",
    "modified_at",
    "unique_id",
}

# Instructor names identify real third parties, and gym_name in activity_data
# is a per-visit location history. Redact both while keeping timestamps,
# durations and counts, which are the actually useful diagnostic signal for
# bug reports. busyness_data's gymLocationName/gymLocationId are deliberately
# NOT redacted here - they're the single configured home gym, already shown
# unredacted as the device name in the HA UI, so redacting them in
# diagnostics would add no privacy and only cost snapshot fragility.
TO_REDACT_ACTIVITY = {"gym_name", "latest_checkin_gym", "instructor"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TheGymGroupConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "busyness_data": runtime_data.busyness.data or {},
        "activity_data": async_redact_data(
            runtime_data.activity.data or {}, TO_REDACT_ACTIVITY
        ),
    }
