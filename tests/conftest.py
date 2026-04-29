"""Common fixtures for The Gym Group tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.the_gym_group.const import DOMAIN

from .const import MOCK_API_DATA, MOCK_CONFIG


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
    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        return_value=MOCK_API_DATA,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
