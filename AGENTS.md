# Repository Guidelines

## Project Structure & Module Organization

This repository is a Home Assistant custom integration for The Gym Group. Runtime code lives in `custom_components/the_gym_group/`: `api.py` wraps the Netpulse API, `coordinator.py` refreshes data, and platform modules such as `sensor.py`, `calendar.py`, and `device_trigger.py` expose Home Assistant entities. Keep integration constants and URL builders in `const.py`; shared device metadata belongs in `entity.py`.

Tests are in `tests/`, generally mirroring their target module (for example, `tests/test_api.py`). Diagnostics snapshots live in `tests/snapshots/`. User-facing translations are in `custom_components/the_gym_group/translations/`; branding assets and dashboard examples are under `brand/`, `branding/`, and `examples/`.

## Build, Test, and Development Commands

Install test dependencies with:

```bash
pip install -r requirements_test.txt
```

Run the complete suite with `pytest tests/ --asyncio-mode=auto`. Run one area while iterating, for example `pytest tests/test_config_flow.py --asyncio-mode=auto`. If a deliberate diagnostics-output change updates a Syrupy snapshot, run `pytest tests/test_diagnostics.py --asyncio-mode=auto --snapshot-update` and review the resulting `.ambr` diff. CI also runs HACS validation and Hassfest.

## Coding Style & Naming Conventions

Use standard Python with four-space indentation, type annotations where they clarify interfaces, and async Home Assistant APIs (`async_*`) for I/O. Follow the existing naming scheme: `TheGymGroup...` for classes, `async_get_...` for API methods, and uppercase names for constants. Keep API parsing and error translation in `api.py` or coordinators rather than sensors. No lint or type-check command is configured; match nearby code and keep imports ordered conventionally.

## Testing Guidelines

Use pytest and `pytest-homeassistant-custom-component`. Mock API-client calls with `unittest.mock.patch`; do not make live Netpulse requests. Name tests `test_<behavior>` and cover success, malformed payload, auth, and connection-error paths where applicable. Reuse fixtures from `tests/conftest.py`, especially `loaded_entry`, and preserve redaction coverage for diagnostics.

The root `conftest.py` and `custom_components/__init__.py` make the local integration discoverable to Home Assistant's test loader; do not remove them. `tests/conftest.py` clears the custom-component scan cache before each test. The known aiohttp teardown error in `test_full_user_flow_success` is caused by a test-dependency mismatch when the test itself passes.

## Architecture & Integration Configuration

`TheGymGroupApiClient` logs in to the Netpulse API and reauthenticates once after a 401/403. The five-minute busyness coordinator powers the population and status sensors; the 30-minute activity coordinator fetches check-ins and schedule data for the remaining sensors and calendar. Store both coordinators in `hass.data[DOMAIN][entry.entry_id]`.

Use the config-entry `entry_id` to scope device and entity IDs—never `gymLocationId`, which can collide across accounts. The config entry's unique ID is the Netpulse user UUID. Credential edits belong in the reconfigure or reauth flows, not an options flow. Forms use `selector.TextSelector`; bare `vol.Email` cannot be serialised by Home Assistant's form renderer.

Keep the minimum Home Assistant version aligned with `hacs.json` (currently 2026.3.0). This is a cloud-polling integration: only HTTPS `netpulse.com` hosts accepted by `is_valid_host()` may be used. Validate stored configuration again during entry setup. Diagnostics must redact usernames, passwords, entry IDs, account UUIDs, instructor names, and visit gym names; credentials must never be logged. Activity timestamps/durations and the configured gym location are intentionally retained—they're the useful diagnostic signal and the gym is already shown unredacted as the HA device name, so redacting it in diagnostics would add no privacy.

## CI and Validation

GitHub Actions runs tests on Python 3.14 for pushes and pull requests to `main`. A separate workflow runs HACS validation and Hassfest on the same events, daily, and manually. Before submitting integration metadata, translations, or brand-asset changes, ensure they remain compatible with both validators.

## Commit & Pull Request Guidelines

Use concise Conventional Commit-style subjects seen in history, such as `fix: validate response shape`, `test: add calendar coverage`, or `docs: update setup guidance`. Keep each commit focused. Pull requests should explain the behavioral change, note test coverage, link relevant issues, and include screenshots for UI, entity, or dashboard-visible changes. Never commit account credentials, PINs, API cookies, or unredacted diagnostics.
