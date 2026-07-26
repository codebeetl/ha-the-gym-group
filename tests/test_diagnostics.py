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


async def test_diagnostics_redacts_pii(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """The account's unique_id and gym/instructor names are redacted."""
    entry = loaded_entry

    diagnostics_data = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics_data["config_entry"]["unique_id"] == "**REDACTED**"

    activity = diagnostics_data["activity_data"]
    assert activity["latest_checkin_gym"] == "**REDACTED**"
    for checkin in activity["calendar_checkins"]:
        assert checkin["gym_name"] == "**REDACTED**"
    for booked_class in activity["calendar_classes"]:
        assert booked_class["instructor"] == "**REDACTED**"
    assert activity["next_class"]["instructor"] == "**REDACTED**"
    # Timestamps/durations stay untouched - they're the useful diagnostic signal.
    assert activity["latest_checkin"] is not None
    assert activity["monthly_hours"] == 0.0
