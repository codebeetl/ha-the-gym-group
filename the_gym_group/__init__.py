"""The Gym Group integration."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TheGymGroupApiClient
from .const import DOMAIN, PLATFORMS
from .coordinator import TheGymGroupDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up The Gym Group from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session: aiohttp.ClientSession = async_get_clientsession(hass)

    api_client: TheGymGroupApiClient = TheGymGroupApiClient(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session
    )

    coordinator: TheGymGroupDataUpdateCoordinator = TheGymGroupDataUpdateCoordinator(
        hass, api_client=api_client
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
