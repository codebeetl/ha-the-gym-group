"""Constants for The Gym Group integration."""

from homeassistant.const import Platform

# The domain of your integration. Should be unique.
DOMAIN = "the_gym_group"

# The platform we are integrating with (sensor).
PLATFORMS: list[Platform] = [Platform.SENSOR]

# API Endpoints
LOGIN_URL = "https://thegymgroup.netpulse.com/np/exerciser/login"
BUSYNESS_URL_TEMPLATE = "https://thegymgroup.netpulse.com/np/thegymgroup/v1.0/exerciser/{user_id}/gym-busyness"

# Default headers for API requests
BASE_HEADERS = {
    "accept": "application/json",
    "accept-encoding": "gzip",
    "connection": "Keep-Alive",
    "host": "thegymgroup.netpulse.com",
    "user-agent": "okhttp/3.12.3",
    "x-np-api-version": "1.5",
    "x-np-app-version": "6.10",
    "x-np-user-agent": "clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid=; applicationName=The Gym Group; applicationVersion=6.10; applicationVersionCode=38",
    "content-type": "application/x-www-form-urlencoded",
}
