"""Config flow for The Gym Group integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, TheGymGroupApiClient
from .const import (
    ADVANCED_FIELDS,
    ADVANCED_FIELD_KEYS,
    CONF_HOST,
    DEFAULT_HOST,
    DOMAIN,
    is_safe_header_value,
    is_valid_host,
)

_LOGGER = logging.getLogger(__name__)

# Reusable selectors. ``TextSelector`` is used (not bare ``str`` / ``vol.Email``)
# because HA's voluptuous_serialize-based form renderer can serialize selectors
# into the spec the frontend needs; bare callables like ``vol.Email`` cannot be
# serialized and cause a 500 when the form is rendered.
_EMAIL_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
)
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)

class _InvalidHost(Exception):
    """Raised when the configured host isn't an allowed Netpulse domain."""


class _InvalidAdvancedField(Exception):
    """Raised when a header override field contains unsafe characters."""


# Passed as description_placeholders to every form that shows advanced fields
# so that data_description strings in translations can reference the current
# built-in defaults without duplicating the values in the translation file.
_ADV_DEFAULTS_PLACEHOLDERS: dict[str, str] = {
    field.placeholder_key: field.default for field in ADVANCED_FIELDS
}


def _clean_advanced(data: dict[str, Any]) -> dict[str, Any]:
    """Drop advanced transport fields with empty/blank values.

    An empty field means "use the code default at runtime". Removing the key
    from stored data lets async_setup_entry fall back to the current DEFAULT_*
    constants, so updated defaults are picked up automatically on next HA start.
    """
    return {
        k: v
        for k, v in data.items()
        if k not in ADVANCED_FIELD_KEYS or (isinstance(v, str) and v.strip())
    }


def _credentials_schema(
    defaults: Mapping[str, Any],
    *,
    include_username: bool = True,
) -> vol.Schema:
    """Build the schema used by both the user and options flows.

    Advanced transport fields use ``suggested_value`` (not ``default``) so that
    clearing a field submits an empty string, which ``_clean_advanced`` then
    strips before saving. A placeholder shows the built-in default as hint text.
    """
    schema: dict[Any, Any] = {}

    if include_username:
        username_default = defaults.get(CONF_USERNAME)
        username_kwargs = {"default": username_default} if username_default is not None else {}
        schema[vol.Required(CONF_USERNAME, **username_kwargs)] = _EMAIL_SELECTOR

    schema[vol.Required(CONF_PASSWORD)] = _PASSWORD_SELECTOR

    for field in ADVANCED_FIELDS:
        schema[
            vol.Optional(
                field.key,
                description={"suggested_value": defaults.get(field.key) or ""},
            )
        ] = str

    return vol.Schema(schema)


async def _try_login(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> TheGymGroupApiClient:
    """Attempt to log in and return the client on success.

    ``user_input`` must contain at least username/password; the advanced
    transport / app-identity fields are optional and fall back to defaults.

    Raises:
        _InvalidHost: the configured host isn't an allowed Netpulse domain.
        _InvalidAdvancedField: an override contains unsafe header characters.
        InvalidAuth: credentials rejected.
        CannotConnect: transport / server error.
    """
    host = user_input.get(CONF_HOST, DEFAULT_HOST)
    if not is_valid_host(host):
        raise _InvalidHost(f"Host not allowed: {host}")

    # Field keys match TheGymGroupApiClient's keyword argument names exactly,
    # so the five overrides can be forwarded as a single kwargs dict.
    advanced_kwargs = {
        field.key: user_input.get(field.key, field.default) for field in ADVANCED_FIELDS
    }
    for key, value in advanced_kwargs.items():
        if key != CONF_HOST and not is_safe_header_value(value):
            raise _InvalidAdvancedField(f"Unsafe value for {key}")
    client = TheGymGroupApiClient(
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
        async_get_clientsession(hass),
        **advanced_kwargs,
    )
    await client.async_login()
    return client


class TheGymGroupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for The Gym Group."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TheGymGroupOptionsFlow:
        """Get the options flow for this handler."""
        return TheGymGroupOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = _clean_advanced(user_input)
            try:
                client = await _try_login(self.hass, cleaned)
            except _InvalidHost:
                errors["base"] = "invalid_host"
            except _InvalidAdvancedField:
                errors["base"] = "invalid_advanced_field"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(client.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=cleaned[CONF_USERNAME], data=cleaned
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(user_input or {}),
            description_placeholders=_ADV_DEFAULTS_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication.

        Single-step reauth: HA routes both the initial display (no user_input)
        and the form submission back to this method via step_id="reauth". Only
        the password is collected - the advanced fields stay as configured.
        """
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            # Merge with the entry's existing data so the advanced fields
            # carry through into the login attempt.
            login_input = {**entry.data, CONF_PASSWORD: password}
            try:
                await _try_login(self.hass, login_input)
            except _InvalidHost:
                errors["base"] = "invalid_host"
            except _InvalidAdvancedField:
                errors["base"] = "invalid_advanced_field"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                # Update only - reload happens via the update_listener
                # registered in async_setup_entry. Calling a reload helper
                # here too would reload the entry twice.
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_PASSWORD: password}
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}
            ),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )


class TheGymGroupOptionsFlow(config_entries.OptionsFlow):
    """Options flow - allows changing stored credentials and transport fields."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options.

        Re-validates credentials (which also exercises the advanced fields, so
        a bad host / user-agent is caught here rather than at the next refresh).
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = _clean_advanced(user_input)
            try:
                client = await _try_login(self.hass, cleaned)
            except _InvalidHost:
                errors["base"] = "invalid_host"
            except _InvalidAdvancedField:
                errors["base"] = "invalid_advanced_field"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                # If the username now maps to a different account, keep the
                # unique_id in sync so HA can still detect duplicates - but
                # first check no other entry already owns that account.
                new_unique_id: str | None = None
                if client.user_id and client.user_id != self.config_entry.unique_id:
                    existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                        DOMAIN, client.user_id
                    )
                    if existing is not None and existing.entry_id != self.config_entry.entry_id:
                        errors["base"] = "already_configured"
                    else:
                        new_unique_id = client.user_id

                if not errors:
                    # Strip all advanced keys from stored data first so that
                    # a user who clears a field removes its override rather
                    # than leaving the old value from entry.data in place.
                    base = {
                        k: v
                        for k, v in self.config_entry.data.items()
                        if k not in ADVANCED_FIELD_KEYS
                    }
                    new_data = {**base, **cleaned}

                    update_kwargs: dict[str, Any] = {"data": new_data}
                    if new_unique_id is not None:
                        update_kwargs["unique_id"] = new_unique_id

                    self.hass.config_entries.async_update_entry(
                        self.config_entry, **update_kwargs
                    )
                    # The update_listener in __init__.py will reload the entry.
                    return self.async_create_entry(title="", data={})

        # Pre-fill from the current entry, with the in-flight user_input
        # taking precedence so users see what they just typed on validation
        # errors.
        defaults = {**self.config_entry.data, **(user_input or {})}
        return self.async_show_form(
            step_id="init",
            data_schema=_credentials_schema(defaults),
            description_placeholders=_ADV_DEFAULTS_PLACEHOLDERS,
            errors=errors,
        )
