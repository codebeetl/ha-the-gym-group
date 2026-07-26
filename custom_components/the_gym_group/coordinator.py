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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: TheGymGroupApiClient,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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
        parsed = datetime.fromisoformat(date_str)
    except ValueError:
        _LOGGER.warning("Could not parse check-in date %r", date_str)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _add_duration(start_dt: datetime, duration_ms: int) -> datetime:
    """Add a real-time elapsed duration to an aware datetime, DST-safe.

    Adding a timedelta directly to a ZoneInfo-aware datetime does wall-clock
    arithmetic, which is wrong for a real elapsed duration when a DST
    transition falls inside the interval. Doing the addition in UTC and
    converting back avoids that.
    """
    end_utc = start_dt.astimezone(timezone.utc) + timedelta(milliseconds=duration_ms)
    return end_utc.astimezone(start_dt.tzinfo)


def _summarize_checkins(
    check_ins: list[dict[str, Any]], now: datetime
) -> dict[str, Any]:
    """Derive all check-in-based stats from parsed real timestamps.

    Each check-in is parsed once via ``_parse_checkin_dt`` and compared as an
    aware datetime rather than a raw string - the API mixes naive and
    offset-aware ``checkInDate`` formats, and lexical string comparison
    doesn't order those consistently with real time.
    """
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    recent_cutoff = now - timedelta(days=35)

    parsed: list[tuple[dict[str, Any], datetime]] = []
    for ci in check_ins:
        start_dt = _parse_checkin_dt(ci)
        if start_dt is not None:
            parsed.append((ci, start_dt))

    latest_raw = max(parsed, key=lambda pair: pair[1])[0] if parsed else None
    monthly = [ci for ci, start_dt in parsed if start_dt >= month_start]
    total_ms = sum(ci.get("duration", 0) for ci in monthly)

    recent_checkins = [
        {
            "datetime": ci["checkInDate"],
            "duration_minutes": (
                round(ci["duration"] / 60_000) if ci.get("duration") else None
            ),
        }
        for ci, start_dt in parsed
        if start_dt >= recent_cutoff
    ]

    calendar_checkins = [
        {
            "start": start_dt,
            "end": _add_duration(start_dt, ci["duration"]) if ci.get("duration") else None,
            "gym_name": ci.get("gymLocationName") or "The Gym Group",
        }
        for ci, start_dt in parsed
    ]

    return {
        "latest_checkin": _parse_checkin_dt(latest_raw),
        "latest_checkin_gym": latest_raw.get("gymLocationName") if latest_raw else None,
        "latest_checkin_duration_minutes": (
            round(latest_raw.get("duration", 0) / 60_000)
            if latest_raw and latest_raw.get("duration")
            else None
        ),
        "checkin_history": recent_checkins,
        "calendar_checkins": calendar_checkins,
        "monthly_visits": len(monthly),
        "monthly_hours": round(total_ms / 3_600_000, 1),
    }


def _find_next_class(
    schedule: list[dict[str, Any]], now: datetime
) -> dict[str, Any] | None:
    """Return a dict of key attributes for the next non-cancelled, not-yet-started class."""
    candidates: list[dict[str, Any]] = []
    for item in schedule:
        brief = item.get("brief", {})
        if brief.get("cancelled", False):
            continue
        start_ms: int = brief.get("startDateTime", 0)
        end_ms: int = brief.get("endDateTime", 0)
        start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        if start_dt <= now:
            continue
        instructor_info = brief.get("instructor") or {}
        candidates.append(
            {
                "start_dt": start_dt,
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: TheGymGroupApiClient,
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_activity",
            update_interval=ACTIVITY_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and aggregate activity data."""
        now = datetime.now(timezone.utc)
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
        checkin_summary = _summarize_checkins(check_ins, now)

        # All upcoming non-cancelled booked classes for the calendar entity.
        calendar_classes: list[dict[str, Any]] = []
        for item in schedule_raw:
            brief = item.get("brief", {})
            if brief.get("cancelled", False):
                continue
            start_ms: int = brief.get("startDateTime", 0)
            end_ms: int = brief.get("endDateTime", 0)
            if not start_ms:
                continue
            instructor_info = brief.get("instructor") or {}
            calendar_classes.append({
                "start": datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc),
                "end": datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc) if end_ms else None,
                "name": brief.get("name") or "Booked Class",
                "instructor": instructor_info.get("fullName") or "",
            })

        return {
            **checkin_summary,
            "calendar_classes": calendar_classes,
            "next_class": _find_next_class(schedule_raw, now),
        }
