"""Tests for the Netpulse API client."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.the_gym_group.api import (
    CannotConnect,
    InvalidAuth,
    TheGymGroupApiClient,
)


def _mock_request(
    status: int, *, json_return: object = None, json_side_effect: Exception | None = None
) -> MagicMock:
    """Build a mock aiohttp request context manager."""
    response = MagicMock()
    response.status = status
    if json_side_effect is not None:
        response.json = AsyncMock(side_effect=json_side_effect)
    else:
        response.json = AsyncMock(return_value=json_return)
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=response)
    context_manager.__aexit__ = AsyncMock(return_value=False)
    return context_manager


async def test_get_busyness_raises_cannot_connect_on_malformed_json() -> None:
    """A 200 response with an unparsable body must not crash the update."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_mock_request(
            200, json_side_effect=json.JSONDecodeError("Expecting value", "", 0)
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
            200, json_side_effect=json.JSONDecodeError("Expecting value", "", 0)
        )
    )
    client = TheGymGroupApiClient("user@example.com", "pw", session)

    with pytest.raises(CannotConnect):
        await client.async_login()


async def test_login_does_not_follow_redirects() -> None:
    """A malicious/compromised host could 307-redirect the login POST elsewhere.

    Following the redirect would forward the plaintext credentials to
    whatever host the response points at, so redirects must be disabled.
    """
    session = MagicMock()
    session.post = MagicMock(
        return_value=_mock_request(200, json_return={"uuid": "fresh-uuid"})
    )
    client = TheGymGroupApiClient("user@example.com", "pw", session)

    await client.async_login()

    _args, kwargs = session.post.call_args
    assert kwargs["allow_redirects"] is False


async def test_get_busyness_does_not_follow_redirects() -> None:
    """A redirected GET could expose user-specific URL paths to another host."""
    session = MagicMock()
    session.get = MagicMock(
        return_value=_mock_request(200, json_return={"currentCapacity": 12})
    )
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="existing-uid"
    )

    await client.async_get_busyness()

    _args, kwargs = session.get.call_args
    assert kwargs["allow_redirects"] is False


async def test_get_busyness_retries_login_once_on_auth_rejection() -> None:
    """A 401 on the first GET triggers exactly one re-login, then a retried GET."""
    session = MagicMock()
    session.post = MagicMock(
        return_value=_mock_request(200, json_return={"uuid": "fresh-uuid"})
    )
    session.get = MagicMock(
        side_effect=[
            _mock_request(401, json_return=None),
            _mock_request(200, json_return={"currentCapacity": 12}),
        ]
    )
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="stale-uid"
    )

    result = await client.async_get_busyness()

    assert result == {"currentCapacity": 12}
    assert session.post.call_count == 1
    assert session.get.call_count == 2
    assert client.user_id == "fresh-uuid"


async def test_get_busyness_raises_invalid_auth_if_still_rejected_after_relogin() -> None:
    """Two consecutive 401s (even after a re-login) surface as InvalidAuth."""
    session = MagicMock()
    session.post = MagicMock(
        return_value=_mock_request(200, json_return={"uuid": "fresh-uuid"})
    )
    session.get = MagicMock(
        side_effect=[
            _mock_request(401, json_return=None),
            _mock_request(401, json_return=None),
        ]
    )
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="stale-uid"
    )

    with pytest.raises(InvalidAuth):
        await client.async_get_busyness()

    assert session.post.call_count == 1
    assert session.get.call_count == 2


async def test_transient_fetch_failure_does_not_log_at_error_level(caplog) -> None:
    """A transient HTTP failure must not log at ERROR/WARNING - the coordinator

    already logs once when the entity becomes unavailable and once on
    recovery; duplicating that at ERROR level on every poll would spam logs.
    """
    session = MagicMock()
    session.get = MagicMock(return_value=_mock_request(503, json_return=None))
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="existing-uid"
    )

    with pytest.raises(CannotConnect):
        await client.async_get_busyness()

    assert not [r for r in caplog.records if r.levelname in ("ERROR", "WARNING")]


async def test_login_raises_cannot_connect_when_response_is_not_an_object() -> None:
    """A 200 login response that's valid JSON but not an object must not crash."""
    session = MagicMock()
    session.post = MagicMock(return_value=_mock_request(200, json_return=["not", "a", "dict"]))
    client = TheGymGroupApiClient("user@example.com", "pw", session)

    with pytest.raises(CannotConnect):
        await client.async_login()


async def test_get_busyness_raises_cannot_connect_when_response_is_not_an_object() -> None:
    """A 200 busyness response that's valid JSON but not an object must not crash."""
    session = MagicMock()
    session.get = MagicMock(return_value=_mock_request(200, json_return=["not", "a", "dict"]))
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="existing-uid"
    )

    with pytest.raises(CannotConnect):
        await client.async_get_busyness()


async def test_get_schedule_raises_cannot_connect_when_response_is_not_a_list() -> None:
    """A 200 schedule response that's valid JSON but not a list must not crash."""
    session = MagicMock()
    session.get = MagicMock(return_value=_mock_request(200, json_return={"not": "a list"}))
    client = TheGymGroupApiClient(
        "user@example.com", "pw", session, user_id="existing-uid"
    )

    with pytest.raises(CannotConnect):
        await client.async_get_schedule(0, 1)
