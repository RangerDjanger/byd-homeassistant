"""Binary sensor platform for the BYD integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pybyd._state_engine import VehicleSnapshot  # noqa: E402
from pybyd.models.realtime import (  # noqa: E402
    ChargingState,
    ConnectState,
    DoorOpenState,
    LockState,
    OnlineState,
    WindowState,
)

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydBaseEntity


def _rt(snapshot: VehicleSnapshot, attr: str) -> Any:
    return getattr(snapshot.realtime, attr, None) if snapshot.realtime else None


@dataclass(frozen=True, kw_only=True)
class BydBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a BYD binary sensor."""

    # Returns True (on), False (off), or None (unknown).
    is_on_fn: Callable[[VehicleSnapshot], bool | None]


def _door_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = _rt(s, attr)
        if value is None or value == DoorOpenState.UNKNOWN:
            return None
        return value == DoorOpenState.OPEN

    return _fn


def _window_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = _rt(s, attr)
        if value is None or value == WindowState.UNKNOWN:
            return None
        return value == WindowState.OPEN

    return _fn


def _lock_open(attr: str) -> Callable[[VehicleSnapshot], bool | None]:
    def _fn(s: VehicleSnapshot) -> bool | None:
        value = _rt(s, attr)
        if value is None or value in (LockState.UNKNOWN, LockState.UNAVAILABLE):
            return None
        # device_class LOCK: on = unlocked
        return value == LockState.UNLOCKED

    return _fn


def _charging_on(s: VehicleSnapshot) -> bool | None:
    value = _rt(s, "charging_state")
    if value is None or value == ChargingState.UNKNOWN:
        return None
    return value == ChargingState.CHARGING


def _plugged_in(s: VehicleSnapshot) -> bool | None:
    value = _rt(s, "connect_state")
    if value is None or value == ConnectState.UNKNOWN:
        return None
    return value == ConnectState.CONNECTED


def _online(s: VehicleSnapshot) -> bool | None:
    value = _rt(s, "online_state")
    if value is None or value == OnlineState.UNKNOWN:
        return None
    return value == OnlineState.ONLINE


BINARY_SENSORS: tuple[BydBinarySensorDescription, ...] = (
    BydBinarySensorDescription(
        key="door_front_left",
        translation_key="door_front_left",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_door_open("left_front_door"),
    ),
    BydBinarySensorDescription(
        key="door_front_right",
        translation_key="door_front_right",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_door_open("right_front_door"),
    ),
    BydBinarySensorDescription(
        key="door_rear_left",
        translation_key="door_rear_left",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_door_open("left_rear_door"),
    ),
    BydBinarySensorDescription(
        key="door_rear_right",
        translation_key="door_rear_right",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=_door_open("right_rear_door"),
    ),
    BydBinarySensorDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=_door_open("trunk_lid"),
    ),
    BydBinarySensorDescription(
        key="window_front_left",
        translation_key="window_front_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_window_open("left_front_window"),
    ),
    BydBinarySensorDescription(
        key="window_front_right",
        translation_key="window_front_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_window_open("right_front_window"),
    ),
    BydBinarySensorDescription(
        key="window_rear_left",
        translation_key="window_rear_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_window_open("left_rear_window"),
    ),
    BydBinarySensorDescription(
        key="window_rear_right",
        translation_key="window_rear_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=_window_open("right_rear_window"),
    ),
    BydBinarySensorDescription(
        key="lock_front_left",
        translation_key="lock_front_left",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_lock_open("left_front_door_lock"),
    ),
    BydBinarySensorDescription(
        key="lock_front_right",
        translation_key="lock_front_right",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_lock_open("right_front_door_lock"),
    ),
    BydBinarySensorDescription(
        key="lock_rear_left",
        translation_key="lock_rear_left",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_lock_open("left_rear_door_lock"),
    ),
    BydBinarySensorDescription(
        key="lock_rear_right",
        translation_key="lock_rear_right",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=_lock_open("right_rear_door_lock"),
    ),
    BydBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_charging_on,
    ),
    BydBinarySensorDescription(
        key="plugged_in",
        translation_key="plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=_plugged_in,
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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD binary sensors."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BydBinarySensor] = []
    for vin in coordinator.cars:
        for description in BINARY_SENSORS:
            entities.append(BydBinarySensor(coordinator, vin, description))
    async_add_entities(entities)


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
