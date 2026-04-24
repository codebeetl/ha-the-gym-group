"""API Client for The Gym Group."""

from __future__ import annotations

import logging
from typing import Any, cast

import aiohttp

from .const import BASE_HEADERS, BUSYNESS_URL_TEMPLATE, LOGIN_URL

_LOGGER = logging.getLogger(__name__)

_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class TheGymGroupApiClientError(Exception):
    """Base exception for API client errors."""


class InvalidAuth(TheGymGroupApiClientError):
    """Exception raised when the server rejects credentials."""


class CannotConnect(TheGymGroupApiClientError):
    """Exception raised when the API is unreachable or returns an unexpected error."""


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
    def user_id(self) -> str:
        """Return the user ID (empty string if not logged in)."""
        return self._user_id

    async def async_login(self) -> bool:
        """Perform login to populate the session's cookie jar and get the user ID.

        Returns:
            True if login was successful.

        Raises:
            InvalidAuth: The server rejected the credentials (401/403).
            CannotConnect: The login failed for transport or other reasons.
        """
        login_headers: dict[str, str] = BASE_HEADERS.copy()
        login_headers["content-type"] = _FORM_CONTENT_TYPE
        creds: dict[str, str] = {"username": self._username, "password": self._password}

        try:
            async with self._session.post(
                LOGIN_URL, data=creds, headers=login_headers, timeout=_REQUEST_TIMEOUT
            ) as response:
                if response.status in (401, 403):
                    _LOGGER.warning(
                        "Login rejected by server with status %s", response.status
                    )
                    raise InvalidAuth(f"Login rejected: {response.status}")
                if response.status != 200:
                    _LOGGER.error("Login failed with status code: %s", response.status)
                    raise CannotConnect(f"Unexpected login status: {response.status}")

                data: dict[str, Any] = await response.json()
                user_id = str(data.get("uuid") or "")
                if not user_id:
                    _LOGGER.error("Login response missing user ID")
                    raise CannotConnect("Login response missing user ID")

                self._user_id = user_id
                _LOGGER.debug("Login successful, session cookie stored")
                return True
        except aiohttp.ClientError as err:
            _LOGGER.error("Error during login request: %s", err)
            raise CannotConnect(f"Login transport error: {err}") from err

    async def _ensure_logged_in(self) -> None:
        """Ensure the client has a user ID, logging in if necessary.

        Raises:
            InvalidAuth: credentials are no longer valid.
            CannotConnect: transport or server error.
        """
        if self._user_id:
            return
        _LOGGER.debug("No user ID; performing initial login")
        await self.async_login()

    async def async_get_busyness(self) -> dict[str, Any]:
        """Fetch the gym busyness data.

        Returns:
            The busyness payload.

        Raises:
            InvalidAuth: authentication failed (surfaced to the coordinator so HA
                can trigger a reauth flow).
            CannotConnect: API returned a non-auth error.
        """
        await self._ensure_logged_in()
        url: str = BUSYNESS_URL_TEMPLATE.format(user_id=self._user_id)

        data = await self._do_get(url)
        if data is not None:
            return data

        # Likely expired session — re-login and retry once.
        _LOGGER.debug("Busyness fetch returned auth error; re-logging in")
        await self.async_login()

        # Rebuild the URL in case user_id changed on re-login.
        url = BUSYNESS_URL_TEMPLATE.format(user_id=self._user_id)
        data = await self._do_get(url)
        if data is None:
            # Credentials no longer valid after a fresh login — bubble up.
            raise InvalidAuth("Authentication still failing after re-login")
        return data

    async def _do_get(self, url: str) -> dict[str, Any] | None:
        """Perform a GET and return JSON, or None if auth was rejected.

        Raises:
            CannotConnect: non-auth HTTP or transport errors.
        """
        try:
            async with self._session.get(url, headers=BASE_HEADERS, timeout=_REQUEST_TIMEOUT) as response:
                if response.status in (401, 403):
                    return None
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch gym busyness data: %s", response.status
                    )
                    raise CannotConnect(f"HTTP {response.status}")
                return cast(dict[str, Any], await response.json())
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching gym busyness data: %s", err)
            raise CannotConnect(f"Transport error: {err}") from err
