"""API Client for The Gym Group."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import aiohttp

from .const import (
    DEFAULT_APPLICATION_NAME,
    DEFAULT_APPLICATION_VERSION,
    DEFAULT_APPLICATION_VERSION_CODE,
    DEFAULT_HOST,
    DEFAULT_USER_AGENT,
    build_busyness_url,
    build_checkin_history_url,
    build_headers,
    build_login_url,
    build_schedule_url,
)

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
        *,
        host: str = DEFAULT_HOST,
        user_agent: str = DEFAULT_USER_AGENT,
        application_name: str = DEFAULT_APPLICATION_NAME,
        application_version: str = DEFAULT_APPLICATION_VERSION,
        application_version_code: str = DEFAULT_APPLICATION_VERSION_CODE,
    ) -> None:
        """Initialize the API client.

        Args:
            username: The user's email address.
            password: The user's password.
            session: An aiohttp session that will manage cookies.
            user_id: Optional user ID to avoid re-login if already known.
            host: The Netpulse host serving the Gym Group API.
            user_agent: The HTTP ``User-Agent`` header value.
            application_name: The app name advertised in ``x-np-user-agent``.
            application_version: The app version advertised in
                ``x-np-app-version`` and ``x-np-user-agent``.
            application_version_code: The numeric app build code advertised in
                ``x-np-user-agent``.
        """
        self._username = username
        self._password = password
        self._session = session
        self._user_id = user_id
        self._host = host
        self._headers: dict[str, str] = build_headers(
            host=host,
            user_agent=user_agent,
            application_name=application_name,
            application_version=application_version,
            application_version_code=application_version_code,
        )
        self._login_url = build_login_url(host)

    @property
    def user_id(self) -> str:
        """Return the user ID (empty string if not logged in)."""
        return self._user_id

    async def async_login(self) -> None:
        """Perform login to populate the session's cookie jar and get the user ID.

        Raises:
            InvalidAuth: The server rejected the credentials (401/403).
            CannotConnect: The login failed for transport or other reasons.
        """
        login_headers: dict[str, str] = self._headers.copy()
        login_headers["content-type"] = _FORM_CONTENT_TYPE
        creds: dict[str, str] = {"username": self._username, "password": self._password}

        try:
            async with self._session.post(
                self._login_url,
                data=creds,
                headers=login_headers,
                timeout=_REQUEST_TIMEOUT,
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
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
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

        Raises:
            InvalidAuth: authentication failed.
            CannotConnect: API returned a non-auth error.
        """
        await self._ensure_logged_in()
        url: str = build_busyness_url(self._user_id, self._host)

        data = await self._do_get(url, "gym busyness")
        if data is not None:
            return cast(dict[str, Any], data)

        _LOGGER.debug("Busyness fetch returned auth error; re-logging in")
        await self.async_login()

        url = build_busyness_url(self._user_id, self._host)
        data = await self._do_get(url, "gym busyness")
        if data is None:
            raise InvalidAuth("Authentication still failing after re-login")
        return cast(dict[str, Any], data)

    async def async_get_checkin_history(
        self, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Fetch check-in history for an ISO date range.

        Raises:
            InvalidAuth: authentication failed.
            CannotConnect: API returned a non-auth error.
        """
        await self._ensure_logged_in()
        url = build_checkin_history_url(self._user_id, start_date, end_date, self._host)

        data = await self._do_get(url, "check-in history")
        if data is not None:
            return cast(dict[str, Any], data)
        _LOGGER.debug("Check-in history fetch returned auth error; re-logging in")
        await self.async_login()

        url = build_checkin_history_url(self._user_id, start_date, end_date, self._host)
        data = await self._do_get(url, "check-in history")
        if data is None:
            raise InvalidAuth("Authentication still failing after re-login")
        return cast(dict[str, Any], data)

    async def async_get_schedule(
        self, start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]:
        """Fetch the user's booked upcoming classes.

        Raises:
            InvalidAuth: authentication failed.
            CannotConnect: API returned a non-auth error.
        """
        await self._ensure_logged_in()
        url = build_schedule_url(self._user_id, start_ms, end_ms, self._host)

        data = await self._do_get(url, "schedule")
        if data is not None:
            return cast(list[dict[str, Any]], data)
        _LOGGER.debug("Schedule fetch returned auth error; re-logging in")
        await self.async_login()

        url = build_schedule_url(self._user_id, start_ms, end_ms, self._host)
        data = await self._do_get(url, "schedule")
        if data is None:
            raise InvalidAuth("Authentication still failing after re-login")
        return cast(list[dict[str, Any]], data)

    async def _do_get(self, url: str, description: str = "data") -> Any | None:
        """Perform a GET and return JSON, or None if auth was rejected.

        Raises:
            CannotConnect: non-auth HTTP or transport errors.
        """
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=_REQUEST_TIMEOUT
            ) as response:
                if response.status in (401, 403):
                    return None
                if response.status != 200:
                    _LOGGER.error(
                        "Failed to fetch %s: HTTP %s", description, response.status
                    )
                    raise CannotConnect(f"HTTP {response.status}")
                return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Error fetching %s: %s", description, err)
            raise CannotConnect(f"Transport error: {err}") from err
