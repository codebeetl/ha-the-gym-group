"""Test The Gym Group diagnostics."""

from custom_components.the_gym_group.diagnostics import (
    async_get_config_entry_diagnostics,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics platform."""
    entry = loaded_entry

    diagnostics_data = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics_data == snapshot
