# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Install dependencies:**
```bash
pip install pytest pytest-homeassistant-custom-component
```

**Run tests:**
```bash
pytest tests/ --asyncio-mode=auto
pytest tests/test_config_flow.py --asyncio-mode=auto   # single test file
pytest tests/test_diagnostics.py --asyncio-mode=auto --snapshot-update  # regenerate syrupy snapshot
```

No lint or type-check tooling is configured in this repo.

## Architecture

This is a Home Assistant custom integration for The Gym Group (a UK gym chain). It polls the Netpulse mobile-app API and exposes six sensor entities per configured account.

**Data flow:**
```
TheGymGroupApiClient (api.py)
  +-- async_get_busyness()           -> TheGymGroupDataUpdateCoordinator (5 min)
  |                                       +-- TheGymGroupBusynessSensor
  |                                       +-- TheGymGroupStatusSensor
  +-- async_get_latest_checkin()     -> TheGymGroupActivityCoordinator (30 min)
  +-- async_get_checkin_history()    ->   +-- TheGymGroupLastCheckinSensor
  +-- async_get_schedule()           ->   +-- TheGymGroupMonthlyVisitsSensor
                                          +-- TheGymGroupMonthlyTimeSensor
                                          +-- TheGymGroupNextClassSensor
```

`hass.data[DOMAIN][entry.entry_id]` is a dict:
```python
{"busyness": TheGymGroupDataUpdateCoordinator, "activity": TheGymGroupActivityCoordinator}
```

**`api.py`** - Thin async HTTP client wrapping the Netpulse API. Login POSTs form data to
`/np/exerciser/login` and stores the session cookie plus the returned `uuid` as `user_id`.
On a 401/403 from any data endpoint it auto-re-logs-in once before raising `InvalidAuth`.
All GET calls go through `_do_get(url, description)` which returns `None` on auth failure
and raises `CannotConnect` on other errors.

**`const.py`** - All configurable defaults and URL builders live here. When The Gym Group
bumps their Android app version and the API starts rejecting requests, update
`DEFAULT_APPLICATION_VERSION` and `DEFAULT_APPLICATION_VERSION_CODE` here (or users can
override via the options flow without a code change).

**`config_flow.py`** - Three flows share `_credentials_schema()` and `_try_login()`:
- `async_step_user` - initial setup; sets the config entry's `unique_id` to `user_id`
  (Netpulse UUID) to prevent duplicate accounts.
- `async_step_reauth` - password-only re-entry; preserves existing advanced transport fields.
- `TheGymGroupOptionsFlow.async_step_init` - full reconfigure including advanced fields;
  re-validates credentials immediately so bad values are caught at save time.

The forms use `selector.TextSelector` rather than bare voluptuous types because HA's form
renderer cannot serialise bare callables like `vol.Email`.

**`coordinator.py`** - Two coordinators:
- `TheGymGroupDataUpdateCoordinator` (5 min): fetches busyness; converts `InvalidAuth` ->
  `ConfigEntryAuthFailed` (triggers HA reauth banner) and `CannotConnect` -> `UpdateFailed`.
- `TheGymGroupActivityCoordinator` (30 min): sequentially fetches latest check-in, monthly
  history, and schedule; parses raw data into typed values (`datetime`, `int`, `float`,
  `dict | None`) before returning to sensors.

**`sensor.py`** - All six sensors extend `_TheGymGroupBaseSensor` which inherits
`CoordinatorEntity`. The base class takes explicit `device_id` and `gym_name` parameters
(resolved once from busyness coordinator data in `async_setup_entry`) so activity sensors
share the same HA device as busyness sensors. The busyness sensor caps `historical` to
`HISTORICAL_ATTR_LIMIT` (24) entries in `extra_state_attributes` to avoid recorder bloat;
the full payload is available via diagnostics.

**`device_trigger.py`** - Four device triggers: `capacity_above` / `capacity_below`
(delegate to `numeric_state` trigger platform) and `status_open` / `status_closed` (delegate
to `state` trigger platform). The translation key constants are imported from `const.py`.

**`diagnostics.py`** - Redacts `username`, `password`, `entry_id`, `created_at`, and
`modified_at` from the config entry before returning the bundle (the last three are
non-deterministic and would break snapshot tests).

## Testing

Tests use `pytest-homeassistant-custom-component` and mock the API client with
`unittest.mock.patch`. Test infrastructure:

- `conftest.py` (root): pre-imports `custom_components` so HA's loader finds our integration
  instead of the phcc testing stub.
- `custom_components/__init__.py`: empty file that makes our package a regular Python package
  so it takes precedence over the phcc namespace package during test discovery.
- `tests/conftest.py`: `_enable_custom_integrations` autouse fixture clears HA's custom
  component scan cache so our integration is discoverable in each test. `loaded_entry`
  fixture mocks all four API calls and returns a fully set-up config entry.
- `tests/__snapshots__/test_diagnostics.ambr`: syrupy snapshot for the diagnostics test.
  Regenerate with `--snapshot-update` if diagnostics output changes.

The `test_full_user_flow_success` test always shows a teardown ERROR (lingering aiohttp
`_run_safe_shutdown_loop` thread). This is a phcc/aiohttp version mismatch, not a code
defect; the test itself PASSES.

## Key constraints

- Minimum HA version: **2024.11.0** (declared in `hacs.json` and `manifest.json`).
- The integration is `iot_class: cloud_polling` with no local device; all data comes from
  `thegymgroup.netpulse.com` over HTTPS.
- Config entry `unique_id` is the Netpulse user UUID - changing accounts via the options
  flow updates `unique_id` so HA's duplicate-detection stays accurate.
- All credentials are stored in the HA config entry store (encrypted at rest by HA); they
  are never logged.
- Activity data (check-ins, schedule) is from the standard Netpulse API. The schedule
  endpoint (`/np/exerciser/{uuid}/schedule`) returns user-booked classes; each item has a
  `brief` wrapper containing `startDateTime` (epoch ms), `endDateTime` (epoch ms),
  `instructor.fullName`, `maxCapacity`, `totalBooked`, and `cancelled` flag.
