"""Service (action) handlers for the BYD integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from pybyd import BydCar, BydError, SeatLevel, SeatPosition
from pybyd.models.control import ClimateScheduleParams
import voluptuous as vol

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BydConfigEntry, BydDataUpdateCoordinator

SERVICE_SET_SEAT_CLIMATE = "set_seat_climate"
SERVICE_SCHEDULE_CLIMATE = "schedule_climate"
SERVICE_SAVE_CHARGING_SCHEDULE = "save_charging_schedule"
SERVICE_VERIFY_COMMAND_ACCESS = "verify_command_access"

_SEAT_POSITIONS = {"driver": SeatPosition.DRIVER, "copilot": SeatPosition.COPILOT}
_SEAT_LEVELS = {"off": SeatLevel.OFF, "low": SeatLevel.LOW, "high": SeatLevel.HIGH}

_SEAT_CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("position"): vol.In(list(_SEAT_POSITIONS)),
        vol.Required("mode"): vol.In(["heat", "ventilation"]),
        vol.Required("level"): vol.In(list(_SEAT_LEVELS)),
    }
)

_SCHEDULE_CLIMATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("temperature"): vol.All(vol.Coerce(float), vol.Range(min=15.0, max=31.0)),
        vol.Required("booking_time"): cv.datetime,
        vol.Optional("time_span", default=3): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
    }
)

_SAVE_CHARGING_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("start_charge_time"): cv.string,
        vol.Required("end_charge_time"): cv.string,
        vol.Optional("charge_way", default="1"): cv.string,
        vol.Optional("enabled", default=True): cv.boolean,
    }
)

_VERIFY_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _resolve(hass: HomeAssistant, device_id: str) -> tuple[BydDataUpdateCoordinator, str, BydCar]:
    """Resolve a device_id to its coordinator, VIN and BydCar."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"Unknown device: {device_id}")

    vin = next((ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None)
    if vin is None:
        raise ServiceValidationError("Selected device is not a BYD vehicle")

    entry: BydConfigEntry
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator = entry.runtime_data
        car = coordinator.cars.get(vin)
        if car is not None:
            return coordinator, vin, car

    raise ServiceValidationError(f"No loaded BYD vehicle for VIN {vin}")


def _command(
    hass: HomeAssistant, build: Callable[[BydCar, ServiceCall], Awaitable[Any]]
) -> Callable[[ServiceCall], Awaitable[None]]:
    """Wrap a pybyd command so it runs through the coordinator's command path."""

    async def _handler(call: ServiceCall) -> None:
        coordinator, vin, car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        await coordinator.async_run_command(vin, lambda: build(car, call))

    return _handler


def _seat_climate(car: BydCar, call: ServiceCall) -> Awaitable[Any]:
    position = _SEAT_POSITIONS[call.data["position"]]
    level = _SEAT_LEVELS[call.data["level"]]
    if call.data["mode"] == "heat":
        return car.seat.heat(position, level)
    return car.seat.ventilation(position, level)


def _schedule_climate(car: BydCar, call: ServiceCall) -> Awaitable[Any]:
    booking_time: datetime = call.data["booking_time"]
    params = ClimateScheduleParams(
        temperature=call.data["temperature"],
        time_span=call.data["time_span"],
        booking_time=int(booking_time.timestamp()),
    )
    return car.hvac.schedule(params)


def _save_charging_schedule(car: BydCar, call: ServiceCall) -> Awaitable[Any]:
    return car.save_charging_schedule(
        start_charge_time=call.data["start_charge_time"],
        end_charge_time=call.data["end_charge_time"],
        charge_way=call.data["charge_way"],
        enabled=call.data["enabled"],
    )


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register BYD actions. Called once from ``async_setup``."""

    async def _verify_command_access(call: ServiceCall) -> None:
        coordinator, vin, _car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        try:
            await coordinator.async_verify_commands(vin)
        except BydError as err:
            raise HomeAssistantError(f"BYD command failed: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SEAT_CLIMATE,
        _command(hass, _seat_climate),
        schema=_SEAT_CLIMATE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCHEDULE_CLIMATE,
        _command(hass, _schedule_climate),
        schema=_SCHEDULE_CLIMATE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_CHARGING_SCHEDULE,
        _command(hass, _save_charging_schedule),
        schema=_SAVE_CHARGING_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_VERIFY_COMMAND_ACCESS, _verify_command_access, schema=_VERIFY_SCHEMA
    )
