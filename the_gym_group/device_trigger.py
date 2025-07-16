"""Provides device triggers for The Gym Group integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import numeric_state, state
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .sensor import TheGymGroupBusynessSensor, TheGymGroupStatusSensor

TRIGGER_TYPES = {"capacity_above", "capacity_below", "status_open", "status_closed"}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_ABOVE): vol.Coerce(int),
        vol.Optional(CONF_BELOW): vol.Coerce(int),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for The Gym Group devices."""
    registry = er.async_get(hass)
    triggers = []

    # Find all entities associated with the device
    for entry in er.async_entries_for_device(registry, device_id):
        # Add numeric triggers for the busyness sensor
        if entry.translation_key == TheGymGroupBusynessSensor.translation_key:
            triggers.extend(
                [
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "capacity_above",
                    },
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "capacity_below",
                    },
                ]
            )
        # Add state triggers for the status sensor
        elif entry.translation_key == TheGymGroupStatusSensor.translation_key:
            triggers.extend(
                [
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "status_open",
                    },
                    {
                        CONF_PLATFORM: "device",
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "status_closed",
                    },
                ]
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: CALLBACK_TYPE,
    automation_info: dict[str, Any],
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]

    if trigger_type in ["capacity_above", "capacity_below"]:
        numeric_state_config = {
            numeric_state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        }
        if trigger_type == "capacity_above":
            numeric_state_config[numeric_state.CONF_ABOVE] = config[CONF_ABOVE]
        else:
            numeric_state_config[numeric_state.CONF_BELOW] = config[CONF_BELOW]

        numeric_state_config = numeric_state.TRIGGER_SCHEMA(numeric_state_config)
        return await numeric_state.async_attach_trigger(
            hass, numeric_state_config, action, automation_info, platform_type="device"
        )

    # Handle status triggers
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }
    if trigger_type == "status_open":
        state_config[state.CONF_TO] = "open"
    else:  # status_closed
        state_config[state.CONF_TO] = "closed"

    state_config = state.TRIGGER_SCHEMA(state_config)
    return await state.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )
