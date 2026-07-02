"""Base entity for the BYD integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pybyd import BydCar, BydError  # noqa: E402
from pybyd._state_engine import VehicleSnapshot  # noqa: E402

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator


class BydBaseEntity(CoordinatorEntity[BydDataUpdateCoordinator]):
    """Common base for all BYD entities, scoped to a single VIN."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str, key: str) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._key = key
        self._attr_unique_id = f"{vin}_{key}"

        meta = coordinator.device_meta(vin)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=meta["name"],
            manufacturer=meta["manufacturer"],
            model=meta["model"],
            sw_version=meta["sw_version"],
            serial_number=vin,
        )

    @property
    def snapshot(self) -> VehicleSnapshot | None:
        """Latest immutable state snapshot for this vehicle."""
        return self.coordinator.get_snapshot(self._vin)

    @property
    def available(self) -> bool:
        """Entity is available when the coordinator has data for this VIN."""
        return super().available and self.snapshot is not None

    @property
    def car(self) -> BydCar:
        """The BydCar aggregate for this VIN."""
        return self.coordinator.cars[self._vin]

    async def async_run_command(self, action: Callable[[], Awaitable[Any]]) -> None:
        """Verify command access, execute an action, and reconcile state.

        Wraps pybyd errors in :class:`HomeAssistantError` so failures surface
        cleanly in the UI, then requests a coordinator refresh.
        """
        try:
            await self.coordinator.async_verify_commands(self._vin)
            await action()
        except BydError as err:
            raise HomeAssistantError(f"BYD command failed: {err}") from err
        await self.coordinator.async_request_refresh()
