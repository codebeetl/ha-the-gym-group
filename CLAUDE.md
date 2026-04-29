# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dependencies:**
```bash
pip install pytest pytest-homeassistant-custom-component
```

**Run tests:**
```bash
pytest tests/
pytest tests/test_config_flow.py   # single test file
```

No lint or type-check tooling is configured in this repo.

## Architecture

This is a Home Assistant custom integration for The Gym Group (a UK gym chain). It polls the Netpulse mobile-app API every 5 minutes and exposes two sensor entities per configured account.

**Data flow:**
```
TheGymGroupApiClient (api.py)
  +-- async_get_busyness() -> JSON payload
       +-- TheGymGroupDataUpdateCoordinator (coordinator.py)   <- 5-min DataUpdateCoordinator
            +-- TheGymGroupBusynessSensor + TheGymGroupStatusSensor (sensor.py)
```

**`api.py`** - Thin async HTTP client wrapping the Netpulse API. Login POSTs form data to `/np/exerciser/login` and stores the session cookie plus the returned `uuid` as `user_id`. Busyness is fetched via a GET to `/np/thegymgroup/v1.0/exerciser/{user_id}/gym-busyness`. On a 401/403 from the busyness endpoint it auto-re-logs-in once before raising `InvalidAuth`.

**`const.py`** - All configurable defaults live here: `DEFAULT_HOST`, `DEFAULT_USER_AGENT`, `DEFAULT_APPLICATION_VERSION`, etc. The `build_headers()` function constructs the composite `x-np-user-agent` header from these values. When The Gym Group bumps their Android app version and the API starts rejecting requests, update `DEFAULT_APPLICATION_VERSION` and `DEFAULT_APPLICATION_VERSION_CODE` here (or users can override via the options flow without a code change).

**`config_flow.py`** - Three flows share `_credentials_schema()` and `_try_login()`:
- `async_step_user` - initial setup; sets the config entry's `unique_id` to `user_id` (Netpulse UUID) to prevent duplicate accounts.
- `async_step_reauth` - password-only re-entry; preserves existing advanced transport fields.
- `TheGymGroupOptionsFlow.async_step_init` - full reconfigure including advanced fields; re-validates credentials immediately so bad values are caught at save time.

The forms use `selector.TextSelector` rather than bare voluptuous types because HA's form renderer cannot serialise bare callables like `vol.Email`.

**`coordinator.py`** - Converts `InvalidAuth` -> `ConfigEntryAuthFailed` (triggers HA reauth banner) and `CannotConnect` -> `UpdateFailed` (marks entities unavailable).

**`sensor.py`** - Both sensors extend `_TheGymGroupBaseSensor` which inherits `CoordinatorEntity`. The busyness sensor caps `historical` to `HISTORICAL_ATTR_LIMIT` (24) entries in `extra_state_attributes` to avoid recorder bloat; the full payload is available via diagnostics.

**`device_trigger.py`** - Four device triggers: `capacity_above` / `capacity_below` (delegate to `numeric_state` trigger platform) and `status_open` / `status_closed` (delegate to `state` trigger platform). The translation key constants (`BUSYNESS_TRANSLATION_KEY`, `STATUS_TRANSLATION_KEY`) are imported from `const.py` by both modules.

**`diagnostics.py`** - Redacts `username` and `password` from the config entry before returning the bundle.

## Testing

Tests use `pytest-homeassistant-custom-component` and mock the API client with `unittest.mock.patch`. The `conftest.py` fixture `mock_setup_entry` patches `async_setup_entry` to avoid needing a real HA instance for config-flow tests. Test constants (mock credentials, `MOCK_USER_ID`) live in `tests/const.py`.

## Key constraints

- Minimum HA version: **2024.11.0** (declared in `hacs.json` and `manifest.json`).
- The integration is `iot_class: cloud_polling` with no local device; all data comes from `thegymgroup.netpulse.com` over HTTPS.
- Config entry `unique_id` is the Netpulse user UUID - changing accounts via the options flow updates `unique_id` so HA's duplicate-detection stays accurate.
- All credentials are stored in the HA config entry store (encrypted at rest by HA); they are never logged.
