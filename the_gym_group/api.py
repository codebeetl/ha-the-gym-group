"""API Client for The Gym Group."""

import logging
from typing import Any, cast

import aiohttp

from .const import BASE_HEADERS, BUSYNESS_URL_TEMPLATE, LOGIN_URL

_LOGGER = logging.getLogger(__name__)


class TheGymGroupApiClientError(Exception):
    """Base exception for API client errors."""


class InvalidAuth(TheGymGroupApiClientError):
    """Exception for invalid authentication."""


class TheGymGroupApiClient:
    """A class for interacting with The Gym Group API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        user_id: str = "",
    ) -> None:
        """Initialize the API client.

        Args:
            username: The user's email address.
            password: The user's password.
            session: An aiohttp session that will manage cookies.
            user_id: Optional user ID to avoid re-login if already known.
        """
        self._username = username
        self._password = password
        self._session = session
        self._user_id = user_id

    @property
    def user_id(self) -> str | None:
        """Return the user ID."""
        return self._user_id

    async def async_login(self) -> bool:
        """Perform login to populate the session's cookie jar and get the user ID.

        Returns:
            True if login was successful, False otherwise.
        """
        login_headers: dict[str, str] = BASE_HEADERS.copy()
        login_headers["content-type"] = "application/x-www-form-urlencoded"
        creds: dict[str, str] = {"username": self._username, "password": self._password}

        try:
            async with self._session.post(
                LOGIN_URL, data=creds, headers=login_headers
            ) as response:
                if response.status != 200:
                    _LOGGER.error("Login failed with status code: %s", response.status)
                    return False

                data: dict[str, Any] = await response.json()
                self._user_id = str(data.get("uuid") or "")

                if self._user_id:
                    _LOGGER.info("Login successful, session cookie stored")
                    return True

                _LOGGER.error("Login failed: Missing user ID in response")
                return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Error during login request: %s", err)
            return False

    async def _ensure_logged_in(self) -> bool:
        """Ensure the client has a user ID, logging in if necessary."""
        if self._user_id:
            return True

        _LOGGER.warning("No user ID found. Attempting to log in")
        return await self.async_login()

    async def _retry_request(self, url: str) -> dict[str, Any] | None:
        """Retry a request after a forced re-login."""
        _LOGGER.warning("Session likely expired. Re-logging in")
        if not await self.async_login():
            _LOGGER.error("Re-login failed")
            return None

        # Retry the request. The session now has the new cookie.
        async with self._session.get(url, headers=BASE_HEADERS) as retry_response:
            if retry_response.status == 200:
                return cast(dict[str, Any], await retry_response.json())
            _LOGGER.error(
                "Failed to fetch data after re-login: %s", retry_response.status
            )
            return None

    async def async_get_busyness(self) -> dict[str, Any] | None:
        """Fetch the gym busyness data.

        Returns:
            The busyness data as a dictionary, or None if an error occurs.
        """
        if not await self._ensure_logged_in():
            return None

        assert self._user_id is not None
        url: str = BUSYNESS_URL_TEMPLATE.format(user_id=self._user_id)

        try:
            # The session object automatically sends the required cookies.
            response = await self._session.get(url, headers=BASE_HEADERS)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching gym busyness data: %s", err)
            return None

        if response.status == 200:
            return cast(dict[str, Any], await response.json())

        if response.status in [401, 403]:
            return await self._retry_request(url)

        _LOGGER.error("Failed to fetch gym busyness data: %s", response.status)
        return None
