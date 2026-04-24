"""Constants for The Gym Group tests."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.the_gym_group.const import (
    CONF_APPLICATION_NAME,
    CONF_APPLICATION_VERSION,
    CONF_APPLICATION_VERSION_CODE,
    CONF_HOST,
    CONF_USER_AGENT,
    DEFAULT_APPLICATION_NAME,
    DEFAULT_APPLICATION_VERSION,
    DEFAULT_APPLICATION_VERSION_CODE,
    DEFAULT_HOST,
    DEFAULT_USER_AGENT,
)

# Includes every key the schema collects so equality assertions against
# entry.data / submitted form data hold after voluptuous fills defaults.
MOCK_CONFIG = {
    CONF_USERNAME: "test@email.com",
    CONF_PASSWORD: "test_password",
    CONF_HOST: DEFAULT_HOST,
    CONF_USER_AGENT: DEFAULT_USER_AGENT,
    CONF_APPLICATION_NAME: DEFAULT_APPLICATION_NAME,
    CONF_APPLICATION_VERSION: DEFAULT_APPLICATION_VERSION,
    CONF_APPLICATION_VERSION_CODE: DEFAULT_APPLICATION_VERSION_CODE,
}

MOCK_USER_ID = "mock-user-id-123"
MOCK_GYM_ID = "mock-gym-id-456"

MOCK_API_DATA = {
    "gymLocationId": MOCK_GYM_ID,
    "gymLocationName": "Test Gym",
    "currentCapacity": 50,
    "currentPercentage": 25,
    "historical": [],
    "status": "open",
}
