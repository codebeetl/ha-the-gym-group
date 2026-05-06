"""The Gym Group integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

from .api import TheGymGroupApiClient
from .const import (
    CONF_APPLICATION_NAME,
    CONF_APPLICATION_VERSION,
    CONF_APPLICATION_VERSION_CODE,
    CONF_HOST,
    CONF_USER_AGENT,
    DEFAULT_APPLICATION_NAME,
    DEFAULT_APPLICATION_VERSION,
    DEFAULT_APPLICATION_VERSION_CODE,
    DEFAULT_HOST,
    DEFAULT_USER_AGENT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TheGymGroupActivityCoordinator, TheGymGroupDataUpdateCoordinator


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entries to the current schema version.

    V1 -> V2: strip the five advanced transport fields from entry.data so they
    fall back to the built-in DEFAULT_* constants at runtime. This is a
    breaking change documented in the v1.3.0 release notes: any genuine
    non-default overrides must be re-entered via Configure after upgrading.
    """
    if config_entry.version == 1:
        _LOGGER.debug("Migrating %s config entry from version 1 to 2", DOMAIN)
        new_data = {
            k: v
            for k, v in config_entry.data.items()
            if k
            not in {
                CONF_HOST,
                CONF_USER_AGENT,
                CONF_APPLICATION_NAME,
                CONF_APPLICATION_VERSION,
                CONF_APPLICATION_VERSION_CODE,
            }
        }
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info(
            "Migrated %s config entry to version 2: advanced transport fields "
            "now use built-in defaults unless explicitly overridden",
            DOMAIN,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up The Gym Group from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    # Pull the configurable transport / app-identity values from the entry,
    # falling back to defaults so entries created before these fields existed
    # continue to work without a migration.
    api_client = TheGymGroupApiClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
        user_id=entry.unique_id or "",
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        user_agent=entry.data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        application_name=entry.data.get(
            CONF_APPLICATION_NAME, DEFAULT_APPLICATION_NAME
        ),
        application_version=entry.data.get(
            CONF_APPLICATION_VERSION, DEFAULT_APPLICATION_VERSION
        ),
        application_version_code=entry.data.get(
            CONF_APPLICATION_VERSION_CODE, DEFAULT_APPLICATION_VERSION_CODE
        ),
    )

    coordinator = TheGymGroupDataUpdateCoordinator(hass, api_client=api_client)
    await coordinator.async_config_entry_first_refresh()

    activity_coordinator = TheGymGroupActivityCoordinator(hass, api_client=api_client)
    await activity_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "busyness": coordinator,
        "activity": activity_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
