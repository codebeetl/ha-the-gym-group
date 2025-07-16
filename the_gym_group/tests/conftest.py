"""Common fixtures for The Gym Group tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.the_gym_group.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
