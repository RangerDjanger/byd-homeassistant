"""Tests for the BYD data update coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pybyd import BydAuthenticationError, BydError, Vehicle
from pybyd._state_engine import VehicleSnapshot
import pytest

from custom_components.byd.const import (
    CONF_CONTROL_PIN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from custom_components.byd.coordinator import BydDataUpdateCoordinator

VIN = "LTEST0000000000"


def _entry(hass: HomeAssistant, *, pin: str | None = "1234") -> ConfigEntry:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    data = {CONF_USERNAME: "driver@example.com", CONF_PASSWORD: "hunter2"}
    if pin is not None:
        data[CONF_CONTROL_PIN] = pin
    entry = MockConfigEntry(domain=DOMAIN, data=data, options={})
    entry.add_to_hass(hass)
    return entry


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
