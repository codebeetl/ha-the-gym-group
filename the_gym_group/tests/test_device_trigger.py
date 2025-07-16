"""Test The Gym Group device triggers."""

# from unittest.mock import patch

from custom_components.the_gym_group.const import DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_get_device_automations,
)

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .const import MOCK_CONFIG, MOCK_GYM_ID


@pytest.fixture
def device_id(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> str:
    """Register a device and return its ID."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    device_entry = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_GYM_ID)},
    )
    return device_entry.id


@pytest.fixture
def busyness_entity_id(
    hass: HomeAssistant, device_id: str, entity_registry: er.EntityRegistry
) -> str:
    """Register a busyness sensor entity and return its ID."""
    return entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_GYM_ID}_busyness",
        device_id=device_id,
        translation_key="busyness",
    ).entity_id


@pytest.fixture
def status_entity_id(
    hass: HomeAssistant, device_id: str, entity_registry: er.EntityRegistry
) -> str:
    """Register a status sensor entity and return its ID."""
    return entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_GYM_ID}_status",
        device_id=device_id,
        translation_key="status",
    ).entity_id


async def test_get_triggers(
    hass: HomeAssistant, device_id: str, busyness_entity_id: str, status_entity_id: str
) -> None:
    """Test that we get the expected triggers from a device."""
    expected_triggers = [
        {"type": "capacity_above", "entity_id": busyness_entity_id, "domain": "sensor"},
        {"type": "capacity_below", "entity_id": busyness_entity_id, "domain": "sensor"},
        {"type": "status_open", "entity_id": status_entity_id, "domain": "sensor"},
        {"type": "status_closed", "entity_id": status_entity_id, "domain": "sensor"},
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_id)
    assert triggers == expected_triggers


async def test_if_fires_on_capacity_above(
    hass: HomeAssistant,
    busyness_entity_id: str,
    device_id: str,
    service_calls: list[ServiceCall],
) -> None:
    """Test for capacity_above trigger."""
    hass.states.async_set(busyness_entity_id, "50")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_id,
                        "entity_id": busyness_entity_id,
                        "type": "capacity_above",
                        "above": 75,
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )

    # Test that it doesn't fire when below the threshold
    hass.states.async_set(busyness_entity_id, "70")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test that it fires when crossing above the threshold
    hass.states.async_set(busyness_entity_id, "80")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_if_fires_on_status_change(
    hass: HomeAssistant,
    status_entity_id: str,
    device_id: str,
    service_calls: list[ServiceCall],
) -> None:
    """Test for status change trigger."""
    hass.states.async_set(status_entity_id, "closed")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_id,
                        "entity_id": status_entity_id,
                        "type": "status_open",
                    },
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )

    # Test that it doesn't fire for other state changes
    hass.states.async_set(status_entity_id, "closing_soon")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Test that it fires when changing to the target state
    hass.states.async_set(status_entity_id, "open")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
