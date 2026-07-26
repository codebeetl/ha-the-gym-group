"""Test The Gym Group sensors."""

from unittest.mock import patch

from custom_components.the_gym_group.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    MOCK_API_DATA,
    MOCK_CHECKIN_HISTORY_DATA,
    MOCK_CONFIG,
    MOCK_SCHEDULE_DATA,
)


async def test_sensor_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities are created with the correct states and attributes."""

    # Look up entities by unique_id rather than a guessed entity_id slug - the
    # slug depends on device_name + translated entity_name and changes across
    # HA versions. unique_id is scoped by config entry (not just gym location)
    # so that two accounts at the same gym don't collide.
    busyness_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{loaded_entry.entry_id}_busyness"
    )
    assert busyness_entry is not None
    busyness_state = hass.states.get(busyness_entry)
    assert busyness_state is not None
    assert busyness_state.state == str(MOCK_API_DATA["currentCapacity"])
    assert (
        busyness_state.attributes["current_percentage"]
        == MOCK_API_DATA["currentPercentage"]
    )

    status_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{loaded_entry.entry_id}_status"
    )
    assert status_entry is not None
    status_state = hass.states.get(status_entry)
    assert status_state is not None
    assert status_state.state == MOCK_API_DATA["status"]


async def test_sensor_unique_id_distinct_across_accounts_at_same_gym(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Two accounts whose home gym is the same location must not collide."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, "username": "second@email.com"},
        unique_id="mock-user-id-second",
        version=2,
    )
    second_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
            return_value=MOCK_API_DATA,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_checkin_history",
            return_value=MOCK_CHECKIN_HISTORY_DATA,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_schedule",
            return_value=MOCK_SCHEDULE_DATA,
        ),
    ):
        await hass.config_entries.async_setup(second_entry.entry_id)
        await hass.async_block_till_done()

    first_busyness = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{loaded_entry.entry_id}_busyness"
    )
    second_busyness = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{second_entry.entry_id}_busyness"
    )
    assert first_busyness is not None
    assert second_busyness is not None
    assert first_busyness != second_busyness
