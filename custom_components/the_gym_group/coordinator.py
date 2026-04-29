"""DataUpdateCoordinator for The Gym Group integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidAuth, TheGymGroupApiClient
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TheGymGroupDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api_client: TheGymGroupApiClient) -> None:
        """Initialize."""
        self.api_client = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.api_client.async_get_busyness()
        except InvalidAuth as err:
            # Triggers Home Assistant's reauth flow.
            raise ConfigEntryAuthFailed(str(err)) from err
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
