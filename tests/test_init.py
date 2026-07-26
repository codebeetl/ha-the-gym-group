"""Test The Gym Group setup process."""

from unittest.mock import patch

from custom_components.the_gym_group.api import InvalidAuth
from custom_components.the_gym_group.const import CONF_HOST, CONF_USER_AGENT, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    MOCK_API_DATA,
    MOCK_CHECKIN_HISTORY_DATA,
    MOCK_CONFIG,
    MOCK_GYM_ID,
    MOCK_SCHEDULE_DATA,
)


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the integration."""
    entry = loaded_entry

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data
    assert entry.runtime_data.busyness
    assert entry.runtime_data.activity

    # Unload - runtime_data should be cleared by the config entry machinery.
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hasattr(entry, "runtime_data")


async def test_setup_entry_gives_each_config_entry_an_isolated_session(
    hass: HomeAssistant,
) -> None:
    """Two accounts must not share a cookie jar.

    The API authenticates purely via session cookies, so if two config
    entries shared Home Assistant's default ClientSession, logging in to
    account B would overwrite account A's session cookie and A's next poll
    would fetch B's data (or vice versa).
    """
    entry_a = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id="user-a", version=2
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, "username": "other@email.com"},
        unique_id="user-b",
        version=2,
    )
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
            return_value=MOCK_API_DATA,
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
        # Setting up the first entry of a domain bootstraps the whole
        # component, which pulls in any other already-added entries of that
        # domain too - so entry_b is set up as a side effect of this call.
        await hass.config_entries.async_setup(entry_a.entry_id)
        await hass.async_block_till_done()

    assert entry_b.state is ConfigEntryState.LOADED

    session_a = entry_a.runtime_data.busyness.api_client._session
    session_b = entry_b.runtime_data.busyness.api_client._session

    assert session_a is not session_b
    assert session_a.cookie_jar is not session_b.cookie_jar

    assert await hass.config_entries.async_unload(entry_a.entry_id)
    assert await hass.config_entries.async_unload(entry_b.entry_id)
    await hass.async_block_till_done()

    assert session_a.closed
    assert session_b.closed


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


async def test_setup_entry_rejects_stored_host_outside_allowed_domain(
    hass: HomeAssistant,
) -> None:
    """A stored entry with an out-of-domain host must not reach the API client.

    Guards against a config entry that predates host validation (or was
    edited outside the options flow) silently posting credentials to an
    arbitrary host on every startup/reload.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: "attacker.example.com"},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_login.assert_not_called()


async def test_setup_entry_rejects_stored_unsafe_advanced_field(
    hass: HomeAssistant,
) -> None:
    """A stored entry with control characters in an advanced field must not

    reach the API client. Guards against a legacy/manually-edited entry that
    predates advanced-field validation.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_USER_AGENT: "evil\r\nX-Injected: true"},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
    ) as mock_login:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_login.assert_not_called()


async def test_setup_migrates_registry_ids_from_gym_location_id_to_entry_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entities/device registered under the old gymLocationId-based unique_id

    scheme are renamed to the current entry-scoped scheme on setup, so
    existing installs keep their entity_id, history, and automations instead
    of getting a duplicate new device.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, version=2)
    entry.add_to_hass(hass)

    old_device_id = MOCK_GYM_ID
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, old_device_id)},
    )
    old_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{old_device_id}_busyness",
        device_id=device.id,
        config_entry=entry,
    )

    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_get_busyness",
            return_value=MOCK_API_DATA,
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

    migrated_entity = entity_registry.async_get(old_entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_busyness"

    migrated_device = device_registry.async_get(device.id)
    assert migrated_device is not None
    assert (DOMAIN, entry.entry_id) in migrated_device.identifiers
    assert (DOMAIN, old_device_id) not in migrated_device.identifiers
