"""Constants for The Gym Group integration."""

from homeassistant.const import Platform

# The domain of your integration. Should be unique.
DOMAIN = "the_gym_group"

# The platform we are integrating with (sensor).
PLATFORMS: list[Platform] = [Platform.SENSOR]

# API Endpoints
LOGIN_URL = "https://thegymgroup.netpulse.com/np/exerciser/login"
BUSYNESS_URL_TEMPLATE = (
    "https://thegymgroup.netpulse.com/np/thegymgroup/v1.0/exerciser/"
    "{user_id}/gym-busyness"
)

# Default headers for API requests.
# NOTE: content-type is deliberately NOT set here. It applies only to the
# form-urlencoded login POST, not to the JSON GETs. The login path adds it
# explicitly.
BASE_HEADERS: dict[str, str] = {
    "accept": "application/json",
    "accept-encoding": "gzip",
    "connection": "Keep-Alive",
    "host": "thegymgroup.netpulse.com",
    "user-agent": "okhttp/3.12.3",
    "x-np-api-version": "1.5",
    "x-np-app-version": "6.10",
    "x-np-user-agent": (
        "clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid=; "
        "applicationName=The Gym Group; applicationVersion=6.10; "
        "applicationVersionCode=38"
    ),
}

# Max number of historical datapoints to expose as a state attribute.
# Full history is available via diagnostics; keeping attributes small avoids
# recorder bloat and the 16 KB attribute warning.
HISTORICAL_ATTR_LIMIT = 24
