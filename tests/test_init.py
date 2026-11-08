"""End-to-end setup/unload tests for the BYD integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from awesomeversion import AwesomeVersion
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from pybyd import BydError, Vehicle
from pybyd._state_engine import VehicleSnapshot
from pybyd.models.charging import ChargingStatus
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.byd.const import (
    CONF_CONTROL_PIN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DOMAIN,
)

VIN = "LTEST0000000000"
DATA = {CONF_USERNAME: "driver@example.com", CONF_PASSWORD: "hunter2", CONF_CONTROL_PIN: "1234"}


def _client(*, login_error: Exception | None = None) -> AsyncMock:
    vehicle = Vehicle(vin=VIN)
    car = MagicMock()
    car.vin = VIN
    car.state = VehicleSnapshot(
        vehicle=vehicle, charging=ChargingStatus(charging_state=1, connect_state=1)
    )
    for name in ("update_realtime", "update_hvac", "update_gps", "update_charging", "update_energy"):
        setattr(car, name, AsyncMock())

    client = AsyncMock()
    client.login = AsyncMock(side_effect=login_error)
    client.get_vehicles = AsyncMock(return_value=[vehicle])
    client.get_car = AsyncMock(return_value=car)
    return client


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="driver@example.com", data=DATA)
    entry.add_to_hass(hass)
    return entry


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """The entry loads, exposes entities and actions, and unloads cleanly."""
    entry = _entry(hass)
    client = _client()
    with patch("custom_components.byd.coordinator.BydClient", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert VIN in entry.runtime_data.cars
    assert hass.services.has_service(DOMAIN, "set_seat_climate")
    charging = [
        s for s in hass.states.async_all("binary_sensor") if s.entity_id.endswith("_charging")
    ]
    assert charging and charging[0].state == "on"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    client.async_close.assert_awaited()


async def test_cloud_outage_at_startup_retries(hass: HomeAssistant) -> None:
    """A BYD outage during setup is retried instead of failing permanently."""
    entry = _entry(hass)
    with patch(
        "custom_components.byd.coordinator.BydClient",
        return_value=_client(login_error=BydError("cloud down")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_change_reloads_entry(hass: HomeAssistant) -> None:
    """Saving options reloads the entry via OptionsFlowWithReload (no update listener)."""
    entry = _entry(hass)
    with patch("custom_components.byd.coordinator.BydClient", return_value=_client()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not entry.update_listeners

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_SCAN_INTERVAL: "300"}
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval.total_seconds() == 300


@pytest.mark.skipif(
    AwesomeVersion(HA_VERSION) < AwesomeVersion("2026.11.0"),
    reason="climate uses the native_* temperature API added in HA 2026.11",
)
async def test_climate_entity_created(hass: HomeAssistant) -> None:
    """Entity-add errors are only logged, so assert the climate entity exists."""
    entry = _entry(hass)
    with patch("custom_components.byd.coordinator.BydClient", return_value=_client()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    climate = hass.states.async_all("climate")
    assert len(climate) == 1
    assert climate[0].attributes["temperature"] == 21.0
