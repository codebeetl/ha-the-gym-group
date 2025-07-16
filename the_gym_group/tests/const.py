"""Constants for The Gym Group tests."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

MOCK_CONFIG = {
    CONF_USERNAME: "test@email.com",
    CONF_PASSWORD: "test_password",
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
