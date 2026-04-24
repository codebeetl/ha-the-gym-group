"""Config flow for The Gym Group integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, TheGymGroupApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _try_login(
    hass: HomeAssistant, username: str, password: str
) -> TheGymGroupApiClient:
    """Attempt to log in and return the client on success.

    Raises:
        InvalidAuth: credentials rejected.
        CannotConnect: transport / server error.
    """
    client = TheGymGroupApiClient(username, password, async_get_clientsession(hass))
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
                client = await _try_login(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): vol.Email(),
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication.

        Single-step reauth: HA routes both the initial display (no user_input)
        and the form submission back to this method via step_id="reauth".
        """
        errors: dict[str, str] = {}
        try:
            entry = self._reauth_entry()
        except ValueError:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            try:
                await _try_login(self.hass, entry.data[CONF_USERNAME], password)
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
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
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
    """Options flow — allows changing the stored credentials."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options, which in this case is re-validating credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = await _try_login(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                new_data = dict(self.config_entry.data)
                new_data[CONF_USERNAME] = user_input[CONF_USERNAME]
                new_data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

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

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=self.config_entry.data.get(CONF_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
