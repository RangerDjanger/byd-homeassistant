"""Binary sensor platform for the BYD integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pybyd._state_engine import VehicleSnapshot
from pybyd.models.realtime import DoorOpenState, LockState, OnlineState, WindowState

from .coordinator import BydConfigEntry, BydDataUpdateCoordinator
from .entity import BydBaseEntity
from .helpers import is_charging, is_plugged_in, rt


@dataclass(frozen=True, kw_only=True)
class BydBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a BYD binary sensor."""

    # Returns True (on), False (off), or None (unknown).
    is_on_fn: Callable[[VehicleSnapshot], bool | None]


def _door_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = rt(s, attr)
        if value is None or value == DoorOpenState.UNKNOWN:
            return None
        return value == DoorOpenState.OPEN

    return _fn


def _window_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = rt(s, attr)
        if value is None or value == WindowState.UNKNOWN:
            return None
        return value == WindowState.OPEN

    return _fn


def _lock_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = rt(s, attr)
        if value is None or value in (LockState.UNKNOWN, LockState.UNAVAILABLE):
            return None
        # device_class LOCK: on = unlocked
        return value == LockState.UNLOCKED

    return _fn


def _online(s: VehicleSnapshot) -> bool | None:
    value = rt(s, "online_state")
    if value is None or value == OnlineState.UNKNOWN:
        return None
    return value == OnlineState.ONLINE


def _door(key: str, attr: str) -> BydBinarySensorDescription:
    return BydBinarySensorDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_door_open(attr),
    )


def _window(key: str, attr: str) -> BydBinarySensorDescription:
    return BydBinarySensorDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_window_open(attr),
    )


def _lock(key: str, attr: str) -> BydBinarySensorDescription:
    return BydBinarySensorDescription(
        key=key,
        translation_key=key,
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_lock_open(attr),
    )


BINARY_SENSORS: tuple[BydBinarySensorDescription, ...] = (
    _door("door_front_left", "left_front_door"),
    _door("door_front_right", "right_front_door"),
    _door("door_rear_left", "left_rear_door"),
    _door("door_rear_right", "right_rear_door"),
    BydBinarySensorDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=_door_open("trunk_lid"),
    ),
    _window("window_front_left", "left_front_window"),
    _window("window_front_right", "right_front_window"),
    _window("window_rear_left", "left_rear_window"),
    _window("window_rear_right", "right_rear_window"),
    _lock("lock_front_left", "left_front_door_lock"),
    _lock("lock_front_right", "right_front_door_lock"),
    _lock("lock_rear_left", "left_rear_door_lock"),
    _lock("lock_rear_right", "right_rear_door_lock"),
    BydBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=is_charging,
    ),
    BydBinarySensorDescription(
        key="plugged_in",
        translation_key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=is_plugged_in,
    ),
    BydBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        is_on_fn=_online,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BydConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BYD binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        BydBinarySensor(coordinator, vin, description)
        for vin in coordinator.cars
        for description in BINARY_SENSORS
    )


class BydBinarySensor(BydBaseEntity, BinarySensorEntity):
    """A BYD binary sensor entity."""

    entity_description: BydBinarySensorDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        description: BydBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return self.entity_description.is_on_fn(snapshot)
