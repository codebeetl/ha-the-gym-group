"""Constants for The Gym Group integration."""

from __future__ import annotations

from homeassistant.const import Platform

# The domain of your integration. Should be unique.
DOMAIN = "the_gym_group"

# The platform we are integrating with (sensor).
PLATFORMS: list[Platform] = [Platform.SENSOR]

# --- Config entry keys for the configurable transport / app-identity values.
#
# These are exposed in the config flow (with sensible defaults) and stored in
# the config entry. Users only need to change them if The Gym Group rotates
# their mobile-app version and the API starts rejecting our headers.
CONF_HOST = "host"
CONF_USER_AGENT = "user_agent"
CONF_APPLICATION_NAME = "application_name"
CONF_APPLICATION_VERSION = "application_version"
CONF_APPLICATION_VERSION_CODE = "application_version_code"

# --- Defaults for the above. These mirror what the official Android app sends
# at the time of writing. If The Gym Group bumps their app version and the
# server starts returning 4xx, update these defaults (or override per-entry
# via the options flow without releasing a new version).
DEFAULT_HOST = "thegymgroup.netpulse.com"
DEFAULT_USER_AGENT = "okhttp/3.12.3"
DEFAULT_APPLICATION_NAME = "The Gym Group"
DEFAULT_APPLICATION_VERSION = "6.10"
DEFAULT_APPLICATION_VERSION_CODE = "38"

# --- API path templates (the host is supplied at runtime).
LOGIN_PATH = "/np/exerciser/login"
BUSYNESS_PATH_TEMPLATE = "/np/thegymgroup/v1.0/exerciser/{user_id}/gym-busyness"

# Static header values that we don't currently need to expose for tweaking.
_STATIC_HEADERS: dict[str, str] = {
    "accept": "application/json",
    "accept-encoding": "gzip",
    "connection": "Keep-Alive",
    "x-np-api-version": "1.5",
}

# Max number of historical datapoints to expose as a state attribute.
# Full history is available via diagnostics; keeping attributes small avoids
# recorder bloat and the 16 KB attribute warning.
HISTORICAL_ATTR_LIMIT = 24


def build_headers(
    *,
    host: str = DEFAULT_HOST,
    user_agent: str = DEFAULT_USER_AGENT,
    application_name: str = DEFAULT_APPLICATION_NAME,
    application_version: str = DEFAULT_APPLICATION_VERSION,
    application_version_code: str = DEFAULT_APPLICATION_VERSION_CODE,
) -> dict[str, str]:
    """Build the HTTP headers used for every API request.

    The ``application_*`` arguments populate both ``x-np-app-version`` and the
    composite ``x-np-user-agent`` header — keeping a single source of truth so
    the two values can never drift.
    """
    return {
        **_STATIC_HEADERS,
        "host": host,
        "user-agent": user_agent,
        "x-np-app-version": application_version,
        "x-np-user-agent": (
            "clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid=; "
            f"applicationName={application_name}; "
            f"applicationVersion={application_version}; "
            f"applicationVersionCode={application_version_code}"
        ),
    }


def build_login_url(host: str = DEFAULT_HOST) -> str:
    """Return the full login URL for the given host."""
    return f"https://{host}{LOGIN_PATH}"


def build_busyness_url(user_id: str, host: str = DEFAULT_HOST) -> str:
    """Return the busyness URL for the given user on the given host."""
    return f"https://{host}{BUSYNESS_PATH_TEMPLATE.format(user_id=user_id)}"
