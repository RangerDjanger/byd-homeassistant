"""Sensor platform for the BYD integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import PressureConverter
from pybyd._state_engine import VehicleSnapshot  # noqa: E402
from pybyd.models.realtime import TirePressureUnit  # noqa: E402

from .const import CONF_PRESSURE_UNIT, DEFAULT_PRESSURE_UNIT, DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydBaseEntity

_TIRE_UNIT_MAP = {
    TirePressureUnit.BAR: UnitOfPressure.BAR,
    TirePressureUnit.PSI: UnitOfPressure.PSI,
    TirePressureUnit.KPA: UnitOfPressure.KPA,
}

# Options-flow pressure unit choice -> HA unit. "default" is absent, meaning
# "keep the unit the vehicle reports".
_PRESSURE_OPT_MAP = {
    "kpa": UnitOfPressure.KPA,
    "psi": UnitOfPressure.PSI,
    "bar": UnitOfPressure.BAR,
}


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    return name.lower() if isinstance(name, str) else str(value)


def _rt(snapshot: VehicleSnapshot, attr: str) -> Any:
    return getattr(snapshot.realtime, attr, None) if snapshot.realtime else None


def _time_to_full(snapshot: VehicleSnapshot) -> int | None:
    rt = snapshot.realtime
    return rt.time_to_full_minutes if rt is not None else None


def _energy_avg(snapshot: VehicleSnapshot) -> Any:
    energy = snapshot.energy
    if energy is None:
        return None
    for section in (energy.cumulative_energy_consumption, energy.nearest_energy_consumption):
        if section is not None and section.avg_ev_consumption is not None:
            return section.avg_ev_consumption
    return None


def _energy_unit(snapshot: VehicleSnapshot) -> str | None:
    energy = snapshot.energy
    if energy is None:
        return None
    for section in (energy.cumulative_energy_consumption, energy.nearest_energy_consumption):
        if section is not None and section.ev_unit:
            return section.ev_unit
    return None


@dataclass(frozen=True, kw_only=True)
class BydSensorDescription(SensorEntityDescription):
    """Describes a BYD sensor."""

    value_fn: Callable[[VehicleSnapshot], Any]
    unit_fn: Callable[[VehicleSnapshot], str | None] | None = None


SENSORS: tuple[BydSensorDescription, ...] = (
    BydSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "elec_percent"),
    ),
    BydSensorDescription(
        key="range",
        translation_key="range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "endurance_mileage"),
    ),
    BydSensorDescription(
        key="total_mileage",
        translation_key="total_mileage",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: _rt(s, "total_mileage"),
    ),
    BydSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "speed"),
    ),
    BydSensorDescription(
        key="cabin_temperature",
        translation_key="cabin_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "temp_in_car"),
    ),
    BydSensorDescription(
        key="hvac_set_temperature",
        translation_key="hvac_set_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda s: _rt(s, "main_setting_temp_new") or _rt(s, "main_setting_temp"),
    ),
    BydSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=["unknown", "not_charging", "charging", "connected"],
        value_fn=lambda s: _enum_name(_rt(s, "charging_state")),
    ),
    BydSensorDescription(
        key="connect_state",
        translation_key="connect_state",
        device_class=SensorDeviceClass.ENUM,
        options=["unknown", "disconnected", "connected"],
        value_fn=lambda s: _enum_name(_rt(s, "connect_state")),
    ),
    BydSensorDescription(
        key="power_gear",
        translation_key="power_gear",
        device_class=SensorDeviceClass.ENUM,
        options=["unknown", "off", "on"],
        value_fn=lambda s: _enum_name(_rt(s, "power_gear")),
    ),
    BydSensorDescription(
        key="online_state",
        translation_key="online_state",
        device_class=SensorDeviceClass.ENUM,
        options=["unknown", "online", "offline"],
        value_fn=lambda s: _enum_name(_rt(s, "online_state")),
    ),
    BydSensorDescription(
        key="time_to_full",
        translation_key="time_to_full",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        value_fn=_time_to_full,
    ),
    BydSensorDescription(
        key="tire_pressure_front_left",
        translation_key="tire_pressure_front_left",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "left_front_tire_pressure"),
        unit_fn=lambda s: _TIRE_UNIT_MAP.get(_rt(s, "tire_press_unit")),
    ),
    BydSensorDescription(
        key="tire_pressure_front_right",
        translation_key="tire_pressure_front_right",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "right_front_tire_pressure"),
        unit_fn=lambda s: _TIRE_UNIT_MAP.get(_rt(s, "tire_press_unit")),
    ),
    BydSensorDescription(
        key="tire_pressure_rear_left",
        translation_key="tire_pressure_rear_left",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "left_rear_tire_pressure"),
        unit_fn=lambda s: _TIRE_UNIT_MAP.get(_rt(s, "tire_press_unit")),
    ),
    BydSensorDescription(
        key="tire_pressure_rear_right",
        translation_key="tire_pressure_rear_right",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _rt(s, "right_rear_tire_pressure"),
        unit_fn=lambda s: _TIRE_UNIT_MAP.get(_rt(s, "tire_press_unit")),
    ),
    BydSensorDescription(
        key="gps_speed",
        translation_key="gps_speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: getattr(s.gps, "speed", None) if s.gps else None,
    ),
    BydSensorDescription(
        key="avg_energy_consumption",
        translation_key="avg_energy_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_energy_avg,
        unit_fn=_energy_unit,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD sensors."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BydSensor] = []
    for vin in coordinator.cars:
        for description in SENSORS:
            entities.append(BydSensor(coordinator, vin, description))
    async_add_entities(entities)


class BydSensor(BydBaseEntity, SensorEntity):
    """A BYD sensor entity."""

    entity_description: BydSensorDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        description: BydSensorDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    def _pressure_target_unit(self) -> str | None:
        """Configured pressure unit for tyre sensors, or None to keep native."""
        if self.entity_description.device_class != SensorDeviceClass.PRESSURE:
            return None
        choice = self.coordinator.config_entry.options.get(
            CONF_PRESSURE_UNIT, DEFAULT_PRESSURE_UNIT
        )
        return _PRESSURE_OPT_MAP.get((choice or "").lower())

    def _native_source_unit(self, snapshot: VehicleSnapshot) -> str | None:
        """Unit the vehicle reports this sensor in."""
        if self.entity_description.unit_fn is not None:
            unit = self.entity_description.unit_fn(snapshot)
            if unit is not None:
                return unit
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        value = self.entity_description.value_fn(snapshot)
        target = self._pressure_target_unit()
        if target is not None and value is not None:
            # BYD reports kPa when the vehicle's own unit is unavailable.
            source = self._native_source_unit(snapshot) or UnitOfPressure.KPA
            if source != target:
                try:
                    return round(PressureConverter.convert(float(value), source, target), 1)
                except (TypeError, ValueError):
                    return value
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        target = self._pressure_target_unit()
        if target is not None:
            return target
        snapshot = self.snapshot
        if snapshot is not None and self.entity_description.unit_fn is not None:
            unit = self.entity_description.unit_fn(snapshot)
            if unit is not None:
                return unit
        return self.entity_description.native_unit_of_measurement
