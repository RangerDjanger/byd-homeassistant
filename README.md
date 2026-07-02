# BYD Integration for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for BYD
vehicles. It wraps the [`pybyd`](https://github.com/jkaberg/pyBYD) async client
(vendored into this repository) to expose vehicle state and remote controls in
Home Assistant, with **realtime MQTT push** updates and an **HTTP polling
fallback**.

> ⚠️ This is an unofficial community integration and is not affiliated with or
> endorsed by BYD.

## Features

Each vehicle on your BYD account is added as a Home Assistant **device**.
Entities are created only for the capabilities your vehicle reports.

- **Sensors** — battery %, range, total mileage, speed, cabin temperature,
  climate set temperature, charging state, charge-cable state, power state,
  online state, time to full charge, all four tyre pressures, GPS speed and
  average energy consumption.
- **Binary sensors** — doors, door locks, windows, trunk, charging, plugged-in
  and online status.
- **Device tracker** — GPS location and heading.
- **Lock** — central locking.
- **Climate** — cabin pre-conditioning (start/stop + target temperature).
- **Switches** — driver/passenger seat heating and ventilation, steering-wheel
  heating, battery heating.
- **Buttons** — find car, flash lights, open/close windows, open/close trunk,
  start charging.
- **Services** — `byd.set_seat_climate`, `byd.schedule_climate`,
  `byd.save_charging_schedule`, `byd.verify_command_access`.

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/RangerDjanger/byd-homeassistant` with category
   **Integration**.
3. Search for **BYD Integration**, install it, and restart Home Assistant.

### Manual

1. Copy `custom_components/byd` into your Home Assistant `config/custom_components`
   directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **BYD Integration**.
3. Enter:
   - **Username** and **Password** — your BYD app credentials.
   - **Control PIN** — required to send remote commands (lock, climate, etc.).
   - **Country code** — the two-letter country code for your account.
   - **API base URL** — leave the default unless you are in a different region.

### Options

After setup, open the integration options to adjust:

- **Polling interval** — how often to poll the BYD cloud (fallback to realtime
  updates). Default 60 seconds, minimum 30.
- **Enable realtime (MQTT) updates** — when enabled, live pushes reduce polling.

## Remote commands and the control PIN

Remote commands require the control PIN to be verified once per session. This
happens automatically the first time a command is issued. You can also verify it
proactively with the `byd.verify_command_access` service.

## Vendored `pybyd`

To avoid an external PyPI dependency, the `pybyd` client is vendored under
`custom_components/byd/_vendor/pybyd`. To refresh it from a local checkout of
the upstream repository:

```bash
python scripts/sync_pybyd.py
```

## Development

```bash
# Lint
python -m ruff check custom_components/byd

# Tests
pip install -r requirements_test.txt
pytest tests -q
```

CI runs [hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/),
[HACS validation](https://github.com/hacs/action), Ruff and the test suite on
every push and pull request.

## License

[MIT](LICENSE)
