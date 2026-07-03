"""Tests for the BYD data update coordinator."""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pybyd import BydAuthenticationError, BydError, Vehicle
from pybyd._state_engine import VehicleSnapshot
from pybyd.models.charging import ChargingStatus
import pytest

from custom_components.byd import coordinator as coordinator_module
from custom_components.byd.const import (
    CONF_CHARGING_SCAN_INTERVAL,
    CONF_CONTROL_PIN,
    CONF_PASSWORD,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_SCAN_INTERVAL,
    CONF_QUIET_START,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.byd.coordinator import (
    BydDataUpdateCoordinator,
    _in_window,
    _parse_time,
)

VIN = "LTEST0000000000"


def _entry(
    hass: HomeAssistant,
    *,
    pin: str | None = "1234",
    options: dict | None = None,
) -> ConfigEntry:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    data = {CONF_USERNAME: "driver@example.com", CONF_PASSWORD: "hunter2"}
    if pin is not None:
        data[CONF_CONTROL_PIN] = pin
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options or {})
    entry.add_to_hass(hass)
    return entry


def _snapshot(*, charging: bool | None = None) -> VehicleSnapshot:
    """Build a snapshot, optionally with a known charging state."""
    charging_status = None
    if charging is not None:
        charging_status = ChargingStatus(charging_state=1 if charging else 0)
    return VehicleSnapshot(vehicle=Vehicle(vin=VIN), charging=charging_status)


def _mock_car() -> MagicMock:
    car = MagicMock()
    car.vin = VIN
    car.state = VehicleSnapshot(vehicle=Vehicle(vin=VIN))
    car.update_realtime = AsyncMock()
    car.update_hvac = AsyncMock()
    car.update_gps = AsyncMock()
    car.update_charging = AsyncMock()
    car.update_energy = AsyncMock()
    return car


async def _setup_coordinator(
    hass: HomeAssistant, coordinator: BydDataUpdateCoordinator, car: MagicMock
) -> None:
    client = AsyncMock()
    client.get_vehicles = AsyncMock(return_value=[Vehicle(vin=VIN)])
    client.get_car = AsyncMock(return_value=car)
    client.verify_command_access = AsyncMock()
    coordinator.client = client
    coordinator.cars = {VIN: car}
    coordinator.vehicles = {VIN: Vehicle(vin=VIN)}


async def test_poll_tolerates_section_failure(hass: HomeAssistant) -> None:
    """A failing optional section does not abort the whole poll."""
    entry = _entry(hass)
    coordinator = BydDataUpdateCoordinator(hass, entry)
    car = _mock_car()
    car.update_gps = AsyncMock(side_effect=BydError("gps unsupported"))
    await _setup_coordinator(hass, coordinator, car)

    data = await coordinator._async_update_data()

    assert VIN in data
    car.update_realtime.assert_awaited_once()
    car.update_energy.assert_awaited_once()


async def test_poll_auth_error_becomes_reauth(hass: HomeAssistant) -> None:
    """An auth failure while polling raises ConfigEntryAuthFailed."""
    entry = _entry(hass)
    coordinator = BydDataUpdateCoordinator(hass, entry)
    car = _mock_car()
    car.update_realtime = AsyncMock(side_effect=BydAuthenticationError("expired"))
    await _setup_coordinator(hass, coordinator, car)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_verify_commands_requires_pin(hass: HomeAssistant) -> None:
    """Without a control PIN, verification raises BydError."""
    entry = _entry(hass, pin=None)
    coordinator = BydDataUpdateCoordinator(hass, entry)
    car = _mock_car()
    await _setup_coordinator(hass, coordinator, car)

    with pytest.raises(BydError):
        await coordinator.async_verify_commands(VIN)


async def test_verify_commands_caches_per_session(hass: HomeAssistant) -> None:
    """Command access is verified once per VIN per session."""
    entry = _entry(hass)
    coordinator = BydDataUpdateCoordinator(hass, entry)
    car = _mock_car()
    await _setup_coordinator(hass, coordinator, car)

    await coordinator.async_verify_commands(VIN)
    await coordinator.async_verify_commands(VIN)

    coordinator.client.verify_command_access.assert_awaited_once_with(VIN)


async def test_handle_state_changed_pushes_snapshot(hass: HomeAssistant) -> None:
    """An MQTT push callback merges into coordinator data."""
    entry = _entry(hass)
    coordinator = BydDataUpdateCoordinator(hass, entry)
    car = _mock_car()
    await _setup_coordinator(hass, coordinator, car)

    snapshot = VehicleSnapshot(vehicle=Vehicle(vin=VIN))
    coordinator._handle_state_changed(VIN, snapshot)

    assert coordinator.get_snapshot(VIN) is snapshot


async def test_device_meta_defaults(hass: HomeAssistant) -> None:
    """device_meta falls back to the manufacturer constant for unknown VINs."""
    entry = _entry(hass)
    coordinator = BydDataUpdateCoordinator(hass, entry)

    meta = coordinator.device_meta("UNKNOWNVIN")

    assert meta["manufacturer"] == "BYD"
    assert meta["name"] == "UNKNOWNVIN"


# ---------------------------------------------------------------------------
# Quiet hours / dynamic polling interval
# ---------------------------------------------------------------------------

QUIET_OPTS = {
    CONF_SCAN_INTERVAL: 60,
    CONF_QUIET_HOURS_ENABLED: True,
    CONF_QUIET_START: "22:00:00",
    CONF_QUIET_END: "07:00:00",
    CONF_QUIET_SCAN_INTERVAL: 1800,
    CONF_CHARGING_SCAN_INTERVAL: 300,
}


def _freeze_now(monkeypatch: pytest.MonkeyPatch, at: dt_time) -> None:
    """Pin ``dt_util.now()`` (as seen by the coordinator) to a fixed time."""
    fixed = datetime(2026, 7, 3, at.hour, at.minute, at.second, tzinfo=timezone.utc)
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: fixed)


def test_parse_time_falls_back_to_default() -> None:
    """A blank/invalid option value falls back to the supplied default."""
    assert _parse_time(None, "22:00:00") == dt_time(22, 0)
    assert _parse_time("not-a-time", "07:30:00") == dt_time(7, 30)
    assert _parse_time("06:15:00", "07:00:00") == dt_time(6, 15)


def test_in_window_same_day() -> None:
    """A non-wrapping window is a simple [start, end) check."""
    assert _in_window(dt_time(10), dt_time(9), dt_time(17)) is True
    assert _in_window(dt_time(17), dt_time(9), dt_time(17)) is False  # end exclusive
    assert _in_window(dt_time(8), dt_time(9), dt_time(17)) is False


def test_in_window_crosses_midnight() -> None:
    """A window where start > end wraps past midnight."""
    start, end = dt_time(22), dt_time(7)
    assert _in_window(dt_time(23), start, end) is True
    assert _in_window(dt_time(2), start, end) is True
    assert _in_window(dt_time(7), start, end) is False  # end exclusive
    assert _in_window(dt_time(12), start, end) is False


def test_interval_charging_uses_charging_interval(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Charging inside the quiet window uses the charging interval, not full speed."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=QUIET_OPTS))
    _freeze_now(monkeypatch, dt_time(2, 0))  # inside the quiet window

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=True)})

    assert interval == timedelta(seconds=300)


def test_interval_charging_outside_window_is_normal(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside quiet hours, charging does not change the normal scan interval."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=QUIET_OPTS))
    _freeze_now(monkeypatch, dt_time(12, 0))

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=True)})

    assert interval == timedelta(seconds=60)


def test_interval_quiet_when_idle_overnight(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside the window and not charging, polling slows to the quiet cadence."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=QUIET_OPTS))
    _freeze_now(monkeypatch, dt_time(2, 0))

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=False)})

    assert interval == timedelta(seconds=1800)


def test_interval_fast_outside_window(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside the quiet window, the normal scan interval applies."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=QUIET_OPTS))
    _freeze_now(monkeypatch, dt_time(12, 0))

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=False)})

    assert interval == timedelta(seconds=60)


def test_interval_ignores_quiet_when_disabled(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With quiet hours off, the time of day is irrelevant."""
    opts = {**QUIET_OPTS, CONF_QUIET_HOURS_ENABLED: False}
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=opts))
    _freeze_now(monkeypatch, dt_time(2, 0))

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=False)})

    assert interval == timedelta(seconds=60)


def test_interval_degenerate_window_is_disabled(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A start == end window is treated as disabled (never quiet)."""
    opts = {**QUIET_OPTS, CONF_QUIET_START: "07:00:00", CONF_QUIET_END: "07:00:00"}
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=opts))
    _freeze_now(monkeypatch, dt_time(7, 0))

    interval = coordinator._compute_update_interval({VIN: _snapshot(charging=False)})

    assert interval == timedelta(seconds=60)


async def test_update_data_applies_quiet_interval(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A full poll cycle re-schedules itself onto the quiet cadence."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass, options=QUIET_OPTS))
    car = _mock_car()
    await _setup_coordinator(hass, coordinator, car)
    _freeze_now(monkeypatch, dt_time(2, 0))

    await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=1800)


def test_scan_interval_default_when_unset(hass: HomeAssistant) -> None:
    """With no options, the coordinator uses the default scan interval."""
    coordinator = BydDataUpdateCoordinator(hass, _entry(hass))
    assert coordinator._scan_interval == DEFAULT_SCAN_INTERVAL
