"""Device triggers for The Gym Group integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import numeric_state, state
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Translation keys used by the sensor entities — kept as module-level constants
# so device_trigger doesn't need to import sensor.py (avoids circular imports
# and removes any dependency on private class attributes).
BUSYNESS_TRANSLATION_KEY = "busyness"
STATUS_TRANSLATION_KEY = "status"

TRIGGER_CAPACITY_ABOVE = "capacity_above"
TRIGGER_CAPACITY_BELOW = "capacity_below"
TRIGGER_STATUS_OPEN = "status_open"
TRIGGER_STATUS_CLOSED = "status_closed"

NUMERIC_TRIGGER_TYPES = {TRIGGER_CAPACITY_ABOVE, TRIGGER_CAPACITY_BELOW}
STATE_TRIGGER_TYPES = {TRIGGER_STATUS_OPEN, TRIGGER_STATUS_CLOSED}
TRIGGER_TYPES = NUMERIC_TRIGGER_TYPES | STATE_TRIGGER_TYPES

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_ABOVE): vol.Coerce(int),
        vol.Optional(CONF_BELOW): vol.Coerce(int),
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config.

    Ensures a threshold is supplied for numeric trigger types. HA calls this
    before ``async_attach_trigger`` when the integration exposes it.
    """
    config = TRIGGER_SCHEMA(config)
    trigger_type = config[CONF_TYPE]

    if trigger_type == TRIGGER_CAPACITY_ABOVE and CONF_ABOVE not in config:
        raise InvalidDeviceAutomationConfig(
            f"'{CONF_ABOVE}' is required for trigger type '{trigger_type}'"
        )
    if trigger_type == TRIGGER_CAPACITY_BELOW and CONF_BELOW not in config:
        raise InvalidDeviceAutomationConfig(
            f"'{CONF_BELOW}' is required for trigger type '{trigger_type}'"
        )

    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for The Gym Group devices."""
    registry = er.async_get(hass)
    triggers: list[dict[str, Any]] = []

    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != Platform.SENSOR:
            continue

        base = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        if entry.translation_key == BUSYNESS_TRANSLATION_KEY:
            triggers.append({**base, CONF_TYPE: TRIGGER_CAPACITY_ABOVE})
            triggers.append({**base, CONF_TYPE: TRIGGER_CAPACITY_BELOW})
        elif entry.translation_key == STATUS_TRANSLATION_KEY:
            triggers.append({**base, CONF_TYPE: TRIGGER_STATUS_OPEN})
            triggers.append({**base, CONF_TYPE: TRIGGER_STATUS_CLOSED})

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger by delegating to the built-in trigger platforms."""
    trigger_type = config[CONF_TYPE]
    entity_id = config[CONF_ENTITY_ID]

    if trigger_type in NUMERIC_TRIGGER_TYPES:
        threshold_key = (
            CONF_ABOVE if trigger_type == TRIGGER_CAPACITY_ABOVE else CONF_BELOW
        )
        if threshold_key not in config:
            raise InvalidDeviceAutomationConfig(
                f"'{threshold_key}' is required for trigger type '{trigger_type}'"
            )
        numeric_config: dict[str, Any] = {
            CONF_PLATFORM: "numeric_state",
            CONF_ENTITY_ID: entity_id,
            threshold_key: config[threshold_key],
        }
        return await numeric_state.async_attach_trigger(
            hass, numeric_config, action, trigger_info, platform_type="device"
        )

    # State triggers (status_open / status_closed)
    target_state = "open" if trigger_type == TRIGGER_STATUS_OPEN else "closed"
    state_config: dict[str, Any] = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: entity_id,
        "to": target_state,
    }
    return await state.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )
