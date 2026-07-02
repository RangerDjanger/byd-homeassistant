"""Tests for BYD platform value/state functions.

These exercise the pure snapshot-to-value helpers on each platform using
real pybyd models. They require no Home Assistant runtime, so they run on
any OS (unlike the socket-dependent integration tests).
"""

from __future__ import annotations

from pybyd import Vehicle
from pybyd._state_engine import VehicleSnapshot
from pybyd.models.energy import (
    CumulativeEnergyConsumption,
    EnergyConsumption,
    NearestEnergyConsumption,
)
from pybyd.models.realtime import (
    ChargingState,
    ConnectState,
    DoorOpenState,
    LockState,
    OnlineState,
    SeatHeatVentState,
    StearingWheelHeat,
    TirePressureUnit,
    VehicleRealtimeData,
    WindowState,
)

import custom_components.byd  # noqa: F401  # ensure package import side effects
from custom_components.byd import binary_sensor, sensor, switch

_VEHICLE = Vehicle(vin="LTEST0000000000")


def _snap(**kwargs) -> VehicleSnapshot:
    return VehicleSnapshot(vehicle=_VEHICLE, **kwargs)


# ---------------------------------------------------------------------------
# sensor
# ---------------------------------------------------------------------------


def test_time_to_full_uses_pybyd_property() -> None:
    snap = _snap(realtime=VehicleRealtimeData(full_hour=2, full_minute=15))
    assert sensor._time_to_full(snap) == 135


def test_time_to_full_none_when_incomplete() -> None:
    snap = _snap(realtime=VehicleRealtimeData(full_hour=None, full_minute=30))
    assert sensor._time_to_full(snap) is None


def test_time_to_full_none_without_realtime() -> None:
    assert sensor._time_to_full(_snap()) is None


def test_energy_avg_reads_cumulative_submodel() -> None:
    energy = EnergyConsumption(
        cumulative_energy_consumption=CumulativeEnergyConsumption(
            avg_ev_consumption=14.2, ev_unit="kWh/100km"
        )
    )
    snap = _snap(energy=energy)
    assert sensor._energy_avg(snap) == 14.2
    assert sensor._energy_unit(snap) == "kWh/100km"


def test_energy_avg_falls_back_to_nearest() -> None:
    energy = EnergyConsumption(
        nearest_energy_consumption=NearestEnergyConsumption(
            avg_ev_consumption=9.9, ev_unit="kWh/100km"
        )
    )
    snap = _snap(energy=energy)
    assert sensor._energy_avg(snap) == 9.9
    assert sensor._energy_unit(snap) == "kWh/100km"


def test_energy_avg_none_when_missing() -> None:
    assert sensor._energy_avg(_snap()) is None
    assert sensor._energy_avg(_snap(energy=EnergyConsumption())) is None
    assert sensor._energy_unit(_snap()) is None


def test_battery_sensor_value_fn() -> None:
    battery = next(d for d in sensor.SENSORS if d.key == "battery")
    snap = _snap(realtime=VehicleRealtimeData(elec_percent=73.0))
    assert battery.value_fn(snap) == 73.0


# ---------------------------------------------------------------------------
# switch
# ---------------------------------------------------------------------------


def test_battery_heat_on_uses_battery_heat_state() -> None:
    on = _snap(realtime=VehicleRealtimeData(battery_heat_state=1))
    off = _snap(realtime=VehicleRealtimeData(battery_heat_state=0))
    unknown = _snap(realtime=VehicleRealtimeData(battery_heat_state=None))
    assert switch._battery_heat_on(on) is True
    assert switch._battery_heat_on(off) is False
    assert switch._battery_heat_on(unknown) is None


def test_steering_on_uses_pybyd_property() -> None:
    on = _snap(realtime=VehicleRealtimeData(steering_wheel_heat_state=StearingWheelHeat.ON))
    off = _snap(realtime=VehicleRealtimeData(steering_wheel_heat_state=StearingWheelHeat.OFF))
    assert switch._steering_on(on) is True
    assert switch._steering_on(off) is False
    assert switch._steering_on(_snap()) is None


def test_seat_on_states() -> None:
    fn = switch._seat_on("main_seat_heat_state")
    assert fn(_snap(realtime=VehicleRealtimeData(main_seat_heat_state=SeatHeatVentState.HIGH)))
    assert fn(_snap(realtime=VehicleRealtimeData(main_seat_heat_state=SeatHeatVentState.LOW)))
    assert (
        fn(_snap(realtime=VehicleRealtimeData(main_seat_heat_state=SeatHeatVentState.OFF)))
        is False
    )
    assert (
        fn(_snap(realtime=VehicleRealtimeData(main_seat_heat_state=SeatHeatVentState.NO_DATA)))
        is None
    )


# ---------------------------------------------------------------------------
# binary_sensor
# ---------------------------------------------------------------------------


def test_door_open_helper() -> None:
    fn = binary_sensor._door_open("left_front_door")
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_door=DoorOpenState.OPEN))) is True
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_door=DoorOpenState.CLOSED))) is False
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_door=DoorOpenState.UNKNOWN))) is None


def test_window_open_helper() -> None:
    fn = binary_sensor._window_open("left_front_window")
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_window=WindowState.OPEN))) is True
    assert (
        fn(_snap(realtime=VehicleRealtimeData(left_front_window=WindowState.CLOSED))) is False
    )


def test_lock_open_helper_reports_unlocked_as_on() -> None:
    fn = binary_sensor._lock_open("left_front_door_lock")
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_door_lock=LockState.UNLOCKED))) is True
    assert fn(_snap(realtime=VehicleRealtimeData(left_front_door_lock=LockState.LOCKED))) is False


def test_charging_and_connectivity_helpers() -> None:
    assert (
        binary_sensor._charging_on(
            _snap(realtime=VehicleRealtimeData(charging_state=ChargingState.CHARGING))
        )
        is True
    )
    assert (
        binary_sensor._plugged_in(
            _snap(realtime=VehicleRealtimeData(connect_state=ConnectState.CONNECTED))
        )
        is True
    )
    assert (
        binary_sensor._online(
            _snap(realtime=VehicleRealtimeData(online_state=OnlineState.ONLINE))
        )
        is True
    )


# ---------------------------------------------------------------------------
# lock (delegates to pybyd realtime.is_locked)
# ---------------------------------------------------------------------------


def test_lock_is_locked_via_realtime_property() -> None:
    locked = VehicleRealtimeData(
        left_front_door_lock=LockState.LOCKED,
        right_front_door_lock=LockState.LOCKED,
        left_rear_door_lock=LockState.LOCKED,
        right_rear_door_lock=LockState.LOCKED,
    )
    unlocked = VehicleRealtimeData(left_front_door_lock=LockState.UNLOCKED)
    assert locked.is_locked is True
    assert unlocked.is_locked is False
    assert VehicleRealtimeData().is_locked is None


# ---------------------------------------------------------------------------
# region endpoint derivation (country dropdown -> base URL)
# ---------------------------------------------------------------------------


def test_base_url_for_country_maps_regions() -> None:
    from custom_components.byd import const

    assert const.base_url_for_country("AU") == "https://dilinkappoversea-au.byd.auto"
    assert const.base_url_for_country("nz") == "https://dilinkappoversea-au.byd.auto"
    assert const.base_url_for_country("GB") == "https://dilinkappoversea-eu.byd.auto"
    # Norway is on the EU node, not the "-no" (Middle East/Africa) node.
    assert const.base_url_for_country("NO") == "https://dilinkappoversea-eu.byd.auto"
    assert const.base_url_for_country("AE") == "https://dilinkappoversea-no.byd.auto"
    # Unknown/empty codes fall back to the default endpoint.
    assert const.base_url_for_country("ZZ") == const.DEFAULT_BASE_URL
    assert const.base_url_for_country(None) == const.DEFAULT_BASE_URL


def test_every_country_maps_to_a_known_node() -> None:
    from custom_components.byd import const

    assert const.DEFAULT_COUNTRY_CODE in const.COUNTRY_TO_BASE_URL
    for code, name, node in const.COUNTRIES:
        assert node in const.NODE_BASE_URLS, f"{code} ({name}) has unknown node {node}"


# ---------------------------------------------------------------------------
# tyre pressure unit option
# ---------------------------------------------------------------------------


def _tire_sensor(pressure_unit: str):
    from unittest.mock import MagicMock

    from custom_components.byd import sensor as sensor_mod

    desc = next(d for d in sensor_mod.SENSORS if d.key == "tire_pressure_front_left")
    coord = MagicMock()
    coord.get_snapshot.return_value = _snap(
        realtime=VehicleRealtimeData(
            left_front_tire_pressure=236.0, tire_press_unit=TirePressureUnit.KPA
        )
    )
    coord.device_meta.return_value = {
        "name": "x",
        "manufacturer": "BYD",
        "model": None,
        "sw_version": None,
    }
    coord.config_entry.options = {"pressure_unit": pressure_unit}
    return sensor_mod.BydSensor(coord, "LTEST0000000000", desc)


def test_tire_pressure_default_keeps_vehicle_unit() -> None:
    ent = _tire_sensor("default")
    assert ent.native_unit_of_measurement == "kPa"
    assert ent.native_value == 236.0


def test_tire_pressure_option_converts_to_psi() -> None:
    ent = _tire_sensor("psi")
    assert ent.native_unit_of_measurement == "psi"
    # 236 kPa ≈ 34.2 psi
    assert 34.0 <= ent.native_value <= 34.4
