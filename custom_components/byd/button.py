"""Button platform for the BYD integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pybyd import BydCar  # noqa: E402

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydBaseEntity


@dataclass(frozen=True, kw_only=True)
class BydButtonDescription(ButtonEntityDescription):
    """Describes a BYD button."""

    press_fn: Callable[[BydCar], Awaitable[Any]]
    capability: str


BUTTONS: tuple[BydButtonDescription, ...] = (
    BydButtonDescription(
        key="find_car",
        translation_key="find_car",
        capability="find_car",
        press_fn=lambda car: car.finder.find(),
    ),
    BydButtonDescription(
        key="flash_lights",
        translation_key="flash_lights",
        capability="flash_lights",
        press_fn=lambda car: car.finder.flash_lights(),
    ),
    BydButtonDescription(
        key="close_windows",
        translation_key="close_windows",
        capability="close_windows",
        press_fn=lambda car: car.windows.close(),
    ),
    BydButtonDescription(
        key="open_windows",
        translation_key="open_windows",
        capability="open_windows",
        press_fn=lambda car: car.windows.open(),
    ),
    BydButtonDescription(
        key="open_trunk",
        translation_key="open_trunk",
        capability="open_trunk",
        press_fn=lambda car: car.trunk.open(),
    ),
    BydButtonDescription(
        key="close_trunk",
        translation_key="close_trunk",
        capability="close_trunk",
        press_fn=lambda car: car.trunk.close(),
    ),
    BydButtonDescription(
        key="start_charging",
        translation_key="start_charging",
        capability="start_charge",
        press_fn=lambda car: car.start_charging(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD buttons."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []
    for vin, car in coordinator.cars.items():
        # A manual refresh/sync button is always offered; it needs no control
        # PIN and no vehicle capability, just a coordinator poll.
        entities.append(BydRefreshButton(coordinator, vin))
        for description in BUTTONS:
            if getattr(car.capabilities, description.capability, None):
                entities.append(BydButton(coordinator, vin, description))
    async_add_entities(entities)


class BydButton(BydBaseEntity, ButtonEntity):
    """A BYD command button entity."""

    entity_description: BydButtonDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        description: BydButtonDescription,
    ) -> None:
        super().__init__(coordinator, vin, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.async_run_command(lambda: self.entity_description.press_fn(self.car))


class BydRefreshButton(BydBaseEntity, ButtonEntity):
    """Manual data refresh (sync) button.

    Triggers an immediate coordinator poll. Unlike the command buttons it
    needs no control PIN, so it works even before a PIN is configured, and it
    stays available after a failed poll so the user can retry.
    """

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "refresh")

    @property
    def available(self) -> bool:
        """Always available so a sync can be forced even after a failed poll."""
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
