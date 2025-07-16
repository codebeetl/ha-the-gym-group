"""Test The Gym Group sensors."""

from unittest.mock import patch

from custom_components.the_gym_group.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_API_DATA, MOCK_CONFIG, MOCK_GYM_ID


async def test_sensor_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the sensor entities are created with the correct states and attributes."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        return_value=MOCK_API_DATA,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Test Busyness Sensor
    busyness_id = "sensor.test_gym_busyness"
    busyness_state = hass.states.get(busyness_id)
    assert busyness_state is not None
    assert busyness_state.state == str(MOCK_API_DATA["currentCapacity"])
    assert (
        busyness_state.attributes["current_percentage"]
        == MOCK_API_DATA["currentPercentage"]
    )

    busyness_entry = entity_registry.async_get(busyness_id)
    assert busyness_entry is not None
    assert busyness_entry.unique_id == f"{MOCK_GYM_ID}_busyness"

    # Test Status Sensor
    status_id = "sensor.test_gym_status"
    status_state = hass.states.get(status_id)
    assert status_state is not None
    assert status_state.state == MOCK_API_DATA["status"]

    status_entry = entity_registry.async_get(status_id)
    assert status_entry is not None
    assert status_entry.unique_id == f"{MOCK_GYM_ID}_status"
