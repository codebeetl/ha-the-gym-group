"""Config flow for The Gym Group integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidAuth, TheGymGroupApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TheGymGroupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for The Gym Group."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TheGymGroupOptionsFlow:
        """Get the options flow for this handler."""
        return TheGymGroupOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                api_client = TheGymGroupApiClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
                if not await api_client.async_login():
                    raise InvalidAuth  # noqa: TRY301

                await self.async_set_unique_id(api_client.user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            assert entry

            try:
                api_client = TheGymGroupApiClient(
                    entry.data[CONF_USERNAME],
                    password,
                    async_get_clientsession(self.hass),
                )
                if not await api_client.async_login():
                    raise InvalidAuth  # noqa: TRY301

                new_data = entry.data.copy()
                new_data[CONF_PASSWORD] = password
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class TheGymGroupOptionsFlow(config_entries.OptionsFlow):
    """Handle an options flow for The Gym Group to allow reconfiguring credentials."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options, which in this case is re-validating credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate the new credentials
                api_client = TheGymGroupApiClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
                if not await api_client.async_login():
                    raise InvalidAuth  # noqa: TRY301

                # Update the main config entry data with the new credentials
                new_data = self.config_entry.data.copy()
                new_data[CONF_USERNAME] = user_input[CONF_USERNAME]
                new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                # The update_listener in __init__.py will reload the entry
                return self.async_create_entry(title="", data={})

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"

        # Show a form asking for both username and password, with username pre-filled.
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=self.config_entry.data.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
