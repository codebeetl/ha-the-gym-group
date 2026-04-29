"""Common fixtures for The Gym Group tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.the_gym_group.const import DOMAIN

# Ensure our custom integration is discoverable in every test.  The phcc hass
# fixture initialises HA with its own testing_config and may cache an empty
# custom-component scan before our integration is looked up.  Requesting the
# phcc-provided enable_custom_integrations fixture clears that cache so the
# next scan uses the custom_components.__path__ we set up in conftest.py.
@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:  # noqa: PT004
    """Auto-use wrapper so every test gets custom integrations enabled."""

from .const import (
    MOCK_API_DATA,
    MOCK_CHECKIN_HISTORY_DATA,
    MOCK_CONFIG,
    MOCK_LATEST_CHECKIN_DATA,
    MOCK_SCHEDULE_DATA,
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.the_gym_group.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def loaded_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up and load the integration; return the config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
            return_value=MOCK_API_DATA,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_latest_checkin",
            return_value=MOCK_LATEST_CHECKIN_DATA,
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
    return entry
