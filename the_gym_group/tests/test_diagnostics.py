"""Test The Gym Group diagnostics."""

from unittest.mock import patch

from custom_components.the_gym_group.const import DOMAIN
from custom_components.the_gym_group.diagnostics import (
    async_get_config_entry_diagnostics,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .const import MOCK_API_DATA, MOCK_CONFIG


async def test_diagnostics(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test diagnostics platform."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        return_value=MOCK_API_DATA,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diagnostics_data = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics_data == snapshot
