"""Test The Gym Group diagnostics."""

from unittest.mock import patch

from custom_components.the_gym_group.const import DOMAIN
from custom_components.the_gym_group.diagnostics import (
    async_get_config_entry_diagnostics,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .const import (
    MOCK_API_DATA,
    MOCK_CHECKIN_HISTORY_DATA,
    MOCK_CONFIG,
    MOCK_SCHEDULE_DATA,
)


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


async def test_diagnostics_drops_unexpected_busyness_fields(
    hass: HomeAssistant,
) -> None:
    """An unvetted field in the busyness payload must not leak into diagnostics.

    busyness_data is allowlisted to known-safe fields, so a future/unexpected
    API field (e.g. something PII-shaped) doesn't show up verbatim.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, version=2)
    entry.add_to_hass(hass)

    leaky_busyness = {**MOCK_API_DATA, "unexpectedField": "should-not-leak"}

    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
            return_value=leaky_busyness,
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diagnostics_data = await async_get_config_entry_diagnostics(hass, entry)

    busyness_data = diagnostics_data["busyness_data"]
    assert "unexpectedField" not in busyness_data
    assert busyness_data["currentCapacity"] == MOCK_API_DATA["currentCapacity"]
    assert busyness_data["gymLocationName"] == MOCK_API_DATA["gymLocationName"]
