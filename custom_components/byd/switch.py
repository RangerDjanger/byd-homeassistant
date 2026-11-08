"""Switch platform for the BYD integration (seat/steering/battery heating)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pybyd import BydCar, SeatLevel, SeatPosition
from pybyd._state_engine import VehicleSnapshot
from pybyd.models.realtime import SeatHeatVentState

from .coordinator import BydConfigEntry, BydDataUpdateCoordinator
from .entity import BydBaseEntity
from .helpers import rt


def _seat_on(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = rt(s, attr)
        if value is None or value in (SeatHeatVentState.UNKNOWN, SeatHeatVentState.NO_DATA):
            return None
        return value in (SeatHeatVentState.LOW, SeatHeatVentState.HIGH)

    return _fn


def _steering_on(s: VehicleSnapshot) -> bool | None:
    return s.realtime.is_steering_wheel_heating if s.realtime else None


def _battery_heat_on(s: VehicleSnapshot) -> bool | None:
    return s.realtime.is_battery_heating if s.realtime else None


@dataclass(frozen=True, kw_only=True)
class BydSwitchDescription(SwitchEntityDescription):
    """Describes a BYD switch."""

    is_on_fn: Callable[[VehicleSnapshot], bool | None]
    turn_on_fn: Callable[[BydCar], Awaitable[Any]]
    turn_off_fn: Callable[[BydCar], Awaitable[Any]]
    capability: str


SWITCHES: tuple[BydSwitchDescription, ...] = (
    BydSwitchDescription(
        key="driver_seat_heat",
        translation_key="driver_seat_heat",
        capability="driver_seat_heat",
        is_on_fn=_seat_on("main_seat_heat_state"),
        turn_on_fn=lambda car: car.seat.heat(SeatPosition.DRIVER, SeatLevel.HIGH),
        turn_off_fn=lambda car: car.seat.heat(SeatPosition.DRIVER, SeatLevel.OFF),
    ),
    BydSwitchDescription(
        key="passenger_seat_heat",
        translation_key="passenger_seat_heat",
        capability="passenger_seat_heat",
        is_on_fn=_seat_on("copilot_seat_heat_state"),
        turn_on_fn=lambda car: car.seat.heat(SeatPosition.COPILOT, SeatLevel.HIGH),
        turn_off_fn=lambda car: car.seat.heat(SeatPosition.COPILOT, SeatLevel.OFF),
    ),
    BydSwitchDescription(
        key="driver_seat_ventilation",
        translation_key="driver_seat_ventilation",
        capability="driver_seat_ventilation",
        is_on_fn=_seat_on("main_seat_ventilation_state"),
        turn_on_fn=lambda car: car.seat.ventilation(SeatPosition.DRIVER, SeatLevel.HIGH),
        turn_off_fn=lambda car: car.seat.ventilation(SeatPosition.DRIVER, SeatLevel.OFF),
    ),
    BydSwitchDescription(
        key="passenger_seat_ventilation",
        translation_key="passenger_seat_ventilation",
        capability="passenger_seat_ventilation",
        is_on_fn=_seat_on("copilot_seat_ventilation_state"),
        turn_on_fn=lambda car: car.seat.ventilation(SeatPosition.COPILOT, SeatLevel.HIGH),
        turn_off_fn=lambda car: car.seat.ventilation(SeatPosition.COPILOT, SeatLevel.OFF),
    ),
    BydSwitchDescription(
        key="steering_wheel_heat",
        translation_key="steering_wheel_heat",
        capability="steering_wheel_heat",
        is_on_fn=_steering_on,
        turn_on_fn=lambda car: car.steering.heat(on=True),
        turn_off_fn=lambda car: car.steering.heat(on=False),
    ),
    BydSwitchDescription(
        key="battery_heat",
        translation_key="battery_heat",
        capability="battery_heat",
        is_on_fn=_battery_heat_on,
        turn_on_fn=lambda car: car.battery.heat(on=True),
        turn_off_fn=lambda car: car.battery.heat(on=False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BydConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BYD switches."""
    coordinator = entry.runtime_data
    entities: list[BydSwitch] = []
    for vin, car in coordinator.cars.items():
        for description in SWITCHES:
            if getattr(car.capabilities, description.capability, None):
                entities.append(BydSwitch(coordinator, vin, description))
    async_add_entities(entities)


class BydSwitch(BydBaseEntity, SwitchEntity):
    """A BYD heating switch entity."""

    entity_description: BydSwitchDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        description: BydSwitchDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return self.entity_description.is_on_fn(snapshot)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_run_command(lambda: self.entity_description.turn_on_fn(self.car))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_run_command(lambda: self.entity_description.turn_off_fn(self.car))
