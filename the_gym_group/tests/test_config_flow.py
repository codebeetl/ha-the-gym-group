"""Test the The Gym Group config flow."""

from unittest.mock import AsyncMock, patch

from custom_components.the_gym_group.api import InvalidAuth
from custom_components.the_gym_group.const import DOMAIN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, MOCK_USER_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user setup flow succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
            return_value=True,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.user_id",
            new_callable=lambda: MOCK_USER_ID,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result2["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test user flow with an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
        side_effect=Exception("Something broke"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow when the account is already configured."""
    entry = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
            return_value=True,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.user_id",
            new_callable=lambda: MOCK_USER_ID,
        ),
    ):
        await hass.config_entries.flow.async_configure(
            entry["flow_id"], user_input=MOCK_CONFIG
        )

    # Try to configure the same account again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
            return_value=True,
        ),
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.user_id",
            new_callable=lambda: MOCK_USER_ID,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the re-authentication flow succeeds."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_USER_ID
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": mock_entry.entry_id}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth"

    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
            return_value=True,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "new_password"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_PASSWORD] == "new_password"
    assert len(mock_reload.mock_calls) == 1


async def test_reauth_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test re-authentication with invalid credentials."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_USER_ID
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": mock_entry.entry_id}
    )
    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "wrong_password"}
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_options_flow_success(hass: HomeAssistant) -> None:
    """Test the options flow (reconfigure) succeeds."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_USER_ID
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    new_config = {CONF_USERNAME: "new@email.com", CONF_PASSWORD: "new_password"}
    with (
        patch(
            "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
            return_value=True,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_config
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert mock_entry.data == new_config
    assert len(mock_reload.mock_calls) == 1


async def test_options_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test options flow with invalid credentials."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_USER_ID
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    with patch(
        "custom_components.the_gym_group.api.TheGymGroupApiClient.async_login",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "new@email.com",
                CONF_PASSWORD: "wrong_password",
            },
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
