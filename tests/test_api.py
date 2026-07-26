"""Tests for the Netpulse API client."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.the_gym_group.api import CannotConnect, TheGymGroupApiClient


def _mock_request(status: int, json_side_effect: Exception) -> MagicMock:
    """Build a mock aiohttp request context manager with a failing .json()."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(side_effect=json_side_effect)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    return context_manager


async def test_get_busyness_raises_cannot_connect_on_malformed_json() -> None:
    """A 200 response with an unparsable body must not crash the update."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_mock_request(
            200, json.JSONDecodeError("Expecting value", "", 0)
        )
    )
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="existing-uid"
    )

    with pytest.raises(CannotConnect):
        await client.async_get_busyness()


async def test_login_raises_cannot_connect_on_malformed_json() -> None:
    """A 200 login response with an unparsable body must not crash setup."""
    session = MagicMock()
    session.post = MagicMock(
        return_value=_mock_request(
            200, json.JSONDecodeError("Expecting value", "", 0)
        )
    )
    client = TheGymGroupApiClient("user@example.com", "pw", session)

    with pytest.raises(CannotConnect):
        await client.async_login()
