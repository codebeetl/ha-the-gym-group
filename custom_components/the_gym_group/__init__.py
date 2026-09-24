"""The Gym Group integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

_LOGGER = logging.getLogger(__name__)

from .api import TheGymGroupApiClient
from .const import (
    ADVANCED_FIELDS,
    ADVANCED_FIELD_KEYS,
    CONF_HOST,
    DEFAULT_HOST,
    DOMAIN,
    PLATFORMS,
    is_safe_header_value,
    is_valid_host,
)
from .coordinator import TheGymGroupActivityCoordinator, TheGymGroupDataUpdateCoordinator


@dataclass
class TheGymGroupRuntimeData:
    """Data stored on the config entry at runtime."""

    busyness: TheGymGroupDataUpdateCoordinator
    activity: TheGymGroupActivityCoordinator


type TheGymGroupConfigEntry = ConfigEntry[TheGymGroupRuntimeData]


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
            k: v for k, v in config_entry.data.items() if k not in ADVANCED_FIELD_KEYS
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


def _migrate_registry_ids(
    hass: HomeAssistant, entry: TheGymGroupConfigEntry, old_device_id: str
) -> None:
    """Rename registry entries from the old gymLocationId-based device_id to

    the current entry-scoped one, so an existing install keeps its entity_id,
    history, and automations instead of getting an orphaned old device and a
    duplicate new one.
    """
    if old_device_id == entry.entry_id:
        return  # device_id was already entry-scoped - nothing to migrate

    device_registry = dr.async_get(hass)
    # async_get_device is deprecated (breaks in HA 2027.8) and its replacement,
    # async_get_device_by_identifier, only exists from HA 2026.8 - so look the
    # device up among this entry's own devices, which works on every supported
    # version and can't match another entry's device.
    old_identifier = (DOMAIN, old_device_id)
    old_device = next(
        (
            device
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if old_identifier in device.identifiers
        ),
        None,
    )
    if old_device is None:
        return  # already migrated, or a fresh install

    entity_registry = er.async_get(hass)
    prefix = f"{old_device_id}_"
    new_identifier = (DOMAIN, entry.entry_id)

    # Two accounts sharing a gym both got their device merged onto the same
    # gymLocationId-keyed device pre-migration (device identity is dedup'd by
    # identifier, not by config entry). Renaming that device in place would
    # steal it out from under the other entry, which hasn't migrated yet -
    # give this entry a fresh device instead and only detach it from the
    # shared one. When the device isn't shared, keep renaming it in place so
    # a single-account install keeps its existing device_id/history.
    other_entries = old_device.config_entries - {entry.entry_id}
    if other_entries:
        target_device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, identifiers={new_identifier}
        )
        device_registry.async_update_device(
            old_device.id, remove_config_entry_id=entry.entry_id
        )
    else:
        target_device = device_registry.async_update_device(
            old_device.id, new_identifiers={new_identifier}
        )

    for reg_entry in er.async_entries_for_device(
        entity_registry, old_device.id, include_disabled_entities=True
    ):
        if reg_entry.config_entry_id != entry.entry_id:
            continue  # belongs to another entry sharing the old device
        if not reg_entry.unique_id.startswith(prefix):
            continue
        suffix = reg_entry.unique_id[len(prefix) :]
        entity_registry.async_update_entity(
            reg_entry.entity_id,
            new_unique_id=f"{entry.entry_id}_{suffix}",
            device_id=target_device.id,
        )

    _LOGGER.info(
        "Migrated %s device/entities from gymLocationId-based IDs to entry-scoped IDs",
        DOMAIN,
    )


async def async_setup_entry(hass: HomeAssistant, entry: TheGymGroupConfigEntry) -> bool:
    """Set up The Gym Group from a config entry."""
    # A dedicated session (not the shared HA default) so each account gets its
    # own cookie jar - the API authenticates purely via session cookies, and
    # sharing a jar across accounts would let one login overwrite another's.
    # auto_cleanup=True registers the session to close on this entry's unload.
    session = async_create_clientsession(hass)

    # Pull the configurable transport / app-identity values from the entry,
    # falling back to defaults so entries created before these fields existed
    # continue to work without a migration.
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    if not is_valid_host(host):
        # Re-checked here (not just in config_flow) because a stored entry
        # can predate this validation or be edited outside the options flow -
        # credentials must never be posted to an unvalidated host.
        raise ConfigEntryError(f"Configured host '{host}' is not an allowed domain")

    # Field keys match TheGymGroupApiClient's keyword argument names exactly,
    # so the five overrides can be forwarded as a single kwargs dict.
    advanced_kwargs = {
        field.key: entry.data.get(field.key, field.default) for field in ADVANCED_FIELDS
    }
    for key, value in advanced_kwargs.items():
        if key != CONF_HOST and not is_safe_header_value(value):
            # Re-checked here (not just in config_flow) for the same reason as
            # the host check above - a stored entry can predate this
            # validation or be edited outside the options flow.
            raise ConfigEntryError(f"Configured {key} contains unsafe characters")
    api_client = TheGymGroupApiClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
        user_id=entry.unique_id or "",
        **advanced_kwargs,
    )

    coordinator = TheGymGroupDataUpdateCoordinator(
        hass, config_entry=entry, api_client=api_client
    )
    await coordinator.async_config_entry_first_refresh()

    old_device_id = str((coordinator.data or {}).get("gymLocationId") or entry.entry_id)
    _migrate_registry_ids(hass, entry, old_device_id)

    activity_coordinator = TheGymGroupActivityCoordinator(
        hass, config_entry=entry, api_client=api_client
    )
    await activity_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TheGymGroupRuntimeData(
        busyness=coordinator, activity=activity_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: TheGymGroupConfigEntry) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TheGymGroupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
