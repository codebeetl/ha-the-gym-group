# The Gym Group — Home Assistant integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/codebeetl/ha-the-gym-group?include_prereleases&sort=semver)](https://github.com/codebeetl/ha-the-gym-group/releases)
[![License](https://img.shields.io/github/license/codebeetl/ha-the-gym-group)](./LICENSE)

Unofficial Home Assistant integration that exposes live occupancy and open/closed
status for your home gym on [The Gym Group](https://www.thegymgroup.com/) (UK).
Poll the mobile app's "gym busyness" endpoint every 5 minutes; drive automations
off how busy the gym is, or whether it's open.

<p align="center"><img src="branding/logo.png" alt="The Gym Group" width="320"></p>

---

## Features

- **Live gym population** — current number of people in the gym (`mdi:weight-lifter`).
- **Gym status** — `open` / `closed` (`mdi:door`).
- **Device triggers** — automate on capacity crossing a threshold, or the gym
  opening/closing.
- **Extra state attributes** — percentage capacity, recent historical data,
  and the gym's location name.
- **Reauth flow** — when your password changes, Home Assistant prompts you to
  re-enter it rather than silently failing.
- **Diagnostics** — one-click download of a redacted diagnostics bundle for
  bug reports.

## Requirements

- Home Assistant **2024.11.0** or newer.
- An account with [The Gym Group](https://www.thegymgroup.com/) (email +
  numeric PIN that you use to sign into the app).
- HACS installed, or willingness to copy files manually.

## Installation

### Option A — HACS (recommended)

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/codebeetl/ha-the-gym-group` with category
   **Integration**.
3. Find **The Gym Group** in the HACS integrations list and click **Download**.
4. Restart Home Assistant.
5. Continue with [Configuration](#configuration).

### Option B — Manual

1. Download the latest release's source zip from
   [Releases](https://github.com/codebeetl/ha-the-gym-group/releases).
2. Copy the `custom_components/the_gym_group/` directory into your Home
   Assistant configuration directory, so you end up with
   `<config>/custom_components/the_gym_group/__init__.py`.
3. Restart Home Assistant.
4. Continue with [Configuration](#configuration).

## Configuration

1. In Home Assistant, go to **Settings → Devices & services → Add integration**.
2. Search for **The Gym Group** and select it.
3. Enter the **email** and **PIN** you use to sign into the mobile app.
4. The integration logs in, identifies your home gym, and creates a device for
   it with two sensor entities.

Everything is configured through the UI — there is **no YAML configuration**.

### Changing credentials later

Open the integration in **Settings → Devices & services**, click **Configure**,
and re-enter the username and password. If the new credentials belong to a
different Gym Group account, the integration will repoint the device at that
account.

### Advanced configuration

The Gym Group's mobile-app backend (Netpulse) cares about the headers the
client sends. The integration ships with values that mirror the official
Android app at the time of release, but if Gym Group bumps their app version
the API can start returning 401/403/4xx until the new version's headers are
sent.

To handle that without releasing a new build of the integration, the setup
form (and the **Configure** options form) exposes the following fields with
sensible defaults:

| Field | Default | What it does |
| --- | --- | --- |
| **API host** | `thegymgroup.netpulse.com` | The Netpulse host the requests go to. Drives the URL **and** the HTTP `Host` header. |
| **User-Agent header** | `okhttp/3.12.3` | Sent as `User-Agent`. The official app uses the OkHttp default. |
| **Application name** | `The Gym Group` | Embedded in the composite `x-np-user-agent` header. |
| **Application version** | `6.10` | Sent as both `x-np-app-version` and the `applicationVersion=` segment of `x-np-user-agent`. |
| **Application version code** | `38` | The numeric build code, embedded in `x-np-user-agent`. |

Most users should leave these alone. If the integration starts failing all
requests with 4xx after a Gym Group app update, install the latest official
Android app, look up its version (Play Store → app → "About") and version
code, and update the two `Application version` fields via **Configure**. The
integration will re-validate against the API as part of saving, so a typo
that breaks login is caught immediately rather than at the next refresh.

## Entities provided

One device per configured account, with two sensors:

| Sensor | Unique ID | Unit | Description |
| --- | --- | --- | --- |
| Gym Population | `<gymLocationId>_busyness` | `people` | Current occupancy returned by the API. |
| Status | `<gymLocationId>_status` | — | `open` or `closed`. |

Both sensors share additional state attributes on **Gym Population**:

| Attribute | Type | Description |
| --- | --- | --- |
| `gym_location_id` | string | Internal ID of your home gym. |
| `gym_location_name` | string | Human-readable gym name (e.g. "Manchester Piccadilly"). |
| `current_percentage` | int | Occupancy expressed as a percentage of capacity. |
| `historical` | list | The most recent occupancy samples from the API (trimmed to 24). |
| `status` | string | Mirrors the Status sensor for convenience. |

## Device automations

Use the **Automations & scenes → Create automation → Device** trigger picker on
the gym device to build automations without writing YAML.

Available trigger types:

| Trigger | Fires when | Needs threshold |
| --- | --- | --- |
| Capacity goes above | Occupancy crosses _above_ a value you pick | Yes |
| Capacity goes below | Occupancy crosses _below_ a value you pick | Yes |
| Status changes to open | Status transitions to `open` | No |
| Status changes to closed | Status transitions to `closed` | No |

### Example 1 — Notify when the gym is quiet

```yaml
alias: Gym is quiet, good time to go
trigger:
  - platform: numeric_state
    entity_id: sensor.gym_population
    below: 20
    for: "00:05:00"
condition:
  - condition: time
    after: "06:00:00"
    before: "22:00:00"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: Gym quiet
      message: "Only {{ states('sensor.gym_population') }} people in the gym."
```

### Example 2 — Announce opening via speakers

```yaml
alias: Gym has opened
trigger:
  - platform: state
    entity_id: sensor.gym_status
    to: open
action:
  - service: tts.google_say
    data:
      entity_id: media_player.kitchen_speaker
      message: "The gym is now open."
```

### Example 3 — Warning when the gym is full

```yaml
alias: Gym is packed
trigger:
  - platform: template
    value_template: "{{ state_attr('sensor.gym_population', 'current_percentage') | int(0) > 85 }}"
    for: "00:10:00"
action:
  - service: notify.mobile_app_my_phone
    data:
      message: "Gym is {{ state_attr('sensor.gym_population', 'current_percentage') }}% full — maybe wait."
```

## Troubleshooting

### "Invalid username or password"

Try signing into the official Gym Group app with the same credentials. If the
app works but the integration doesn't, download a diagnostics bundle
(**Settings → Devices & services → The Gym Group → ⋮ → Download diagnostics**)
and open an issue.

### Entities are "unavailable" or the population is `unknown`

Check the Home Assistant log (**Settings → System → Logs**) for entries from
`custom_components.the_gym_group`. Transient API errors are logged at `ERROR`;
successful polls at `DEBUG`.

Enable debug logging for the integration:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.the_gym_group: debug
```

Restart Home Assistant to apply.

### Reauth loop after changing your PIN

The integration raises a reauth flow when the API rejects your credentials.
Open **Settings → Devices & services**, click the "Repair" banner, and enter
your new PIN.

## Diagnostics

The integration supports Home Assistant diagnostics. The downloaded bundle
contains:

- The config entry (with **username and password redacted**).
- The most recent API payload (gym location, capacity, status, historical
  samples).

Please include the diagnostics file when opening bug reports — it's the fastest
way to reproduce issues.

## Development

### Running the tests

```bash
pip install pytest pytest-homeassistant-custom-component
pytest tests/
```

### Project layout

```
ha-the-gym-group/
├── hacs.json                          HACS metadata
├── custom_components/the_gym_group/   Integration package
│   ├── __init__.py                    Entry point (setup/unload)
│   ├── api.py                         Thin HTTP client for the Netpulse API
│   ├── config_flow.py                 UI setup, reauth, options
│   ├── coordinator.py                 DataUpdateCoordinator (5-minute polling)
│   ├── sensor.py                      Busyness + Status sensors
│   ├── device_trigger.py              Capacity / status device triggers
│   ├── diagnostics.py                 Redacted diagnostics bundle
│   └── translations/                  UI strings
└── tests/                             pytest-homeassistant-custom-component suite
```

### Contributing

Issues and PRs welcome at
[github.com/codebeetl/ha-the-gym-group](https://github.com/codebeetl/ha-the-gym-group).
Before opening a PR:

1. Run `pytest tests/`.
2. Keep the scope of the PR small; describe what you changed and why.

## Credits

- API endpoint discovery and reverse engineering: **[luke0x90/thegymgroup-api]**
  (https://github.com/luke0x90/thegymgroup-api).
- Built on top of the excellent
  [Home Assistant custom component template](https://developers.home-assistant.io/docs/creating_integration_manifest).

## Disclaimer

This integration is **unofficial** and not affiliated with or endorsed by The
Gym Group. It uses the same HTTP endpoints as the official mobile app. The
endpoints are undocumented and can change or disappear without notice. Use at
your own discretion; keep API usage polite (the integration polls once every
five minutes).

Your credentials are stored by Home Assistant in the same way as any other
integration (encrypted at rest in the config entry store); they are transmitted
only to `thegymgroup.netpulse.com` over HTTPS.

## License

[MIT](./LICENSE)
