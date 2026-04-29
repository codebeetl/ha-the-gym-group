"""Test The Gym Group sensors."""

from custom_components.the_gym_group.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_API_DATA, MOCK_GYM_ID


async def test_sensor_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities are created with the correct states and attributes."""

    # Look up entities by unique_id rather than a guessed entity_id slug - the
    # slug depends on device_name + translated entity_name and changes across
    # HA versions.
    busyness_entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_GYM_ID}_busyness"
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
        "sensor", DOMAIN, f"{MOCK_GYM_ID}_status"
    )
    assert status_entry is not None
    status_state = hass.states.get(status_entry)
    assert status_state is not None
    assert status_state.state == MOCK_API_DATA["status"]
