"""DataUpdateCoordinator for The Gym Group integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, InvalidAuth, TheGymGroupApiClient
from .const import ACTIVITY_SCAN_INTERVAL, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TheGymGroupDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching busyness data from the API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api_client: TheGymGroupApiClient) -> None:
        """Initialize."""
        self.api_client = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            return await self.api_client.async_get_busyness()
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


def _parse_checkin_dt(raw: dict[str, Any] | None) -> datetime | None:
    """Convert a raw check-in object to a timezone-aware datetime, or None."""
    if not raw:
        return None
    date_str: str = raw.get("checkInDate", "")
    tz_name: str = raw.get("timezone", "UTC")
    if not date_str:
        return None
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        tz = timezone.utc
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=tz)
    except ValueError:
        _LOGGER.warning("Could not parse check-in date %r", date_str)
        return None


def _find_next_class(schedule: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return a dict of key attributes for the next non-cancelled booked class."""
    candidates: list[dict[str, Any]] = []
    for item in schedule:
        brief = item.get("brief", {})
        if brief.get("cancelled", False):
            continue
        start_ms: int = brief.get("startDateTime", 0)
        end_ms: int = brief.get("endDateTime", 0)
        instructor_info = brief.get("instructor") or {}
        candidates.append(
            {
                "start_dt": datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc),
                "name": brief.get("name", ""),
                "instructor": instructor_info.get("fullName", ""),
                "available_spots": (
                    brief.get("maxCapacity", 0) - brief.get("totalBooked", 0)
                ),
                "duration_minutes": (
                    round((end_ms - start_ms) / 60_000) if end_ms > start_ms else None
                ),
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["start_dt"])
    return candidates[0]


class TheGymGroupActivityCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for activity data: check-in history and booked schedule."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api_client: TheGymGroupApiClient) -> None:
        """Initialize."""
        self.api_client = api_client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_activity",
            update_interval=ACTIVITY_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and aggregate activity data."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        history_start = now - timedelta(days=365)
        week_end = now + timedelta(days=7)

        try:
            history_raw = await self.api_client.async_get_checkin_history(
                history_start.strftime("%Y-%m-%dT%H:%M:%S"),
                now.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            schedule_raw = await self.api_client.async_get_schedule(
                int(now.timestamp() * 1000),
                int(week_end.timestamp() * 1000),
            )
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        check_ins: list[dict[str, Any]] = history_raw.get("checkIns", [])

        # Most recent entry across the full history window.
        latest_raw = (
            max(check_ins, key=lambda ci: ci.get("checkInDate", ""))
            if check_ins
            else None
        )

        # Monthly stats: filter to the current calendar month.
        month_start_str = month_start.strftime("%Y-%m-%dT%H:%M:%S")
        monthly = [ci for ci in check_ins if ci.get("checkInDate", "") >= month_start_str]
        total_ms = sum(ci.get("duration", 0) for ci in monthly)

        return {
            "latest_checkin": _parse_checkin_dt(latest_raw),
            "latest_checkin_gym": (
                latest_raw.get("gymLocationName") if latest_raw else None
            ),
            "latest_checkin_duration_minutes": (
                round(latest_raw.get("duration", 0) / 60_000)
                if latest_raw and latest_raw.get("duration")
                else None
            ),
            "monthly_visits": len(monthly),
            "monthly_hours": round(total_ms / 3_600_000, 1),
            "next_class": _find_next_class(schedule_raw),
        }
