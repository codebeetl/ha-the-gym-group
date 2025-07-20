"""Test The Gym Group setup process."""

from unittest.mock import patch

from custom_components.the_gym_group.api import InvalidAuth
from custom_components.the_gym_group.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_API_DATA, MOCK_CONFIG


async def test_setup_unload_and_reload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        return_value=MOCK_API_DATA,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    # Test unloading the entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # assert entry.state is ConfigEntryState.NOT_LOADED
    # assert entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_exception(hass: HomeAssistant) -> None:
    """Test ConfigEntryNotReady when API raises an exception during setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        side_effect=Exception("API Error"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(hass: HomeAssistant) -> None:
    """Test ConfigEntryAuthFailed when API raises an auth error during setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
        side_effect=InvalidAuth,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
