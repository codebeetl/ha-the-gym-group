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


def _credentials_schema(
    defaults: Mapping[str, Any],
    *,
    include_username: bool = True,
) -> vol.Schema:
    """Build the schema used by both the user and options flows.

    ``defaults`` is consulted for pre-fill values for every field. Falls back
    to the module-level DEFAULT_* constants when a key is missing.
    """
    schema: dict[Any, Any] = {}

    if include_username:
        username_default = defaults.get(CONF_USERNAME)
        username_kwargs = {"default": username_default} if username_default is not None else {}
        schema[vol.Required(CONF_USERNAME, **username_kwargs)] = _EMAIL_SELECTOR

    schema[vol.Required(CONF_PASSWORD)] = _PASSWORD_SELECTOR

    schema[
        vol.Optional(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST))
    ] = str
    schema[
        vol.Optional(
            CONF_USER_AGENT, default=defaults.get(CONF_USER_AGENT, DEFAULT_USER_AGENT)
        )
    ] = str
    schema[
        vol.Optional(
            CONF_APPLICATION_NAME,
            default=defaults.get(CONF_APPLICATION_NAME, DEFAULT_APPLICATION_NAME),
        )
    ] = str
    schema[
        vol.Optional(
            CONF_APPLICATION_VERSION,
            default=defaults.get(CONF_APPLICATION_VERSION, DEFAULT_APPLICATION_VERSION),
        )
    ] = str
    schema[
        vol.Optional(
            CONF_APPLICATION_VERSION_CODE,
            default=defaults.get(
                CONF_APPLICATION_VERSION_CODE, DEFAULT_APPLICATION_VERSION_CODE
            ),
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
        InvalidAuth: credentials rejected.
        CannotConnect: transport / server error.
    """
    client = TheGymGroupApiClient(
        user_input[CONF_USERNAME],
        user_input[CONF_PASSWORD],
        async_get_clientsession(hass),
        host=user_input.get(CONF_HOST, DEFAULT_HOST),
        user_agent=user_input.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        application_name=user_input.get(
            CONF_APPLICATION_NAME, DEFAULT_APPLICATION_NAME
        ),
        application_version=user_input.get(
            CONF_APPLICATION_VERSION, DEFAULT_APPLICATION_VERSION
        ),
        application_version_code=user_input.get(
            CONF_APPLICATION_VERSION_CODE, DEFAULT_APPLICATION_VERSION_CODE
        ),
    )
    await client.async_login()
    return client


class TheGymGroupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for The Gym Group."""

    VERSION = 1

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
            try:
                client = await _try_login(self.hass, user_input)
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
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(user_input or {}),
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
        try:
            entry = self._reauth_entry()
        except ValueError:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            # Merge with the entry's existing data so the advanced fields
            # carry through into the login attempt.
            login_input = {**entry.data, CONF_PASSWORD: password}
            try:
                await _try_login(self.hass, login_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                new_data = {**entry.data, CONF_PASSWORD: password}
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD): _PASSWORD_SELECTOR}
            ),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    def _reauth_entry(self) -> ConfigEntry:
        """Return the config entry being reauthenticated."""
        entry_id = self.context["entry_id"]
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            raise ValueError(f"Reauth entry {entry_id} not found")
        return entry


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
            try:
                client = await _try_login(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                new_data = {**self.config_entry.data, **user_input}

                # If the username now maps to a different account, keep the
                # unique_id in sync so HA can still detect duplicates.
                update_kwargs: dict[str, Any] = {"data": new_data}
                if client.user_id and client.user_id != self.config_entry.unique_id:
                    update_kwargs["unique_id"] = client.user_id

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
            errors=errors,
        )
