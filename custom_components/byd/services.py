"""Service handlers for the BYD integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from pybyd import BydCar, BydError, SeatLevel, SeatPosition  # noqa: E402
from pybyd.models.control import ClimateScheduleParams  # noqa: E402
import voluptuous as vol

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BydDataUpdateCoordinator

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
        vol.Required("temperature"): vol.All(
            vol.Coerce(float), vol.Range(min=15.0, max=31.0)
        ),
        vol.Required("booking_time"): cv.datetime,
        vol.Optional("time_span", default=3): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=5)
        ),
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


def _resolve(
    hass: HomeAssistant, device_id: str
) -> tuple[BydDataUpdateCoordinator, str, BydCar]:
    """Resolve a device_id to its coordinator, VIN and BydCar."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"Unknown device: {device_id}")

    vin = next(
        (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
    )
    if vin is None:
        raise ServiceValidationError("Selected device is not a BYD vehicle")

    for coordinator in hass.data.get(DOMAIN, {}).values():
        car = coordinator.cars.get(vin)
        if car is not None:
            return coordinator, vin, car

    raise ServiceValidationError(f"No loaded BYD vehicle for VIN {vin}")


async def _run(coordinator: BydDataUpdateCoordinator, vin: str, coro) -> None:
    """Verify command access, run a pybyd coroutine, then refresh."""
    try:
        await coordinator.async_verify_commands(vin)
        await coro
    except BydError as err:
        raise HomeAssistantError(f"BYD command failed: {err}") from err
    await coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register BYD services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_SEAT_CLIMATE):
        return

    async def _set_seat_climate(call: ServiceCall) -> None:
        coordinator, vin, car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        position = _SEAT_POSITIONS[call.data["position"]]
        level = _SEAT_LEVELS[call.data["level"]]
        if call.data["mode"] == "heat":
            await _run(coordinator, vin, car.seat.heat(position, level))
        else:
            await _run(coordinator, vin, car.seat.ventilation(position, level))

    async def _schedule_climate(call: ServiceCall) -> None:
        coordinator, vin, car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        booking_time: datetime = call.data["booking_time"]
        params = ClimateScheduleParams(
            temperature=call.data["temperature"],
            time_span=call.data["time_span"],
            booking_time=int(booking_time.timestamp()),
        )
        await _run(coordinator, vin, car.hvac.schedule(params))

    async def _save_charging_schedule(call: ServiceCall) -> None:
        coordinator, vin, car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        await _run(
            coordinator,
            vin,
            car.save_charging_schedule(
                start_charge_time=call.data["start_charge_time"],
                end_charge_time=call.data["end_charge_time"],
                charge_way=call.data["charge_way"],
                enabled=call.data["enabled"],
            ),
        )

    async def _verify_command_access(call: ServiceCall) -> None:
        coordinator, vin, _car = _resolve(hass, call.data[ATTR_DEVICE_ID])
        try:
            await coordinator.async_verify_commands(vin)
        except BydError as err:
            raise HomeAssistantError(f"BYD command failed: {err}") from err

    hass.services.async_register(
        DOMAIN, SERVICE_SET_SEAT_CLIMATE, _set_seat_climate, schema=_SEAT_CLIMATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCHEDULE_CLIMATE, _schedule_climate, schema=_SCHEDULE_CLIMATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_CHARGING_SCHEDULE,
        _save_charging_schedule,
        schema=_SAVE_CHARGING_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_VERIFY_COMMAND_ACCESS, _verify_command_access, schema=_VERIFY_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove BYD services."""
    for service in (
        SERVICE_SET_SEAT_CLIMATE,
        SERVICE_SCHEDULE_CLIMATE,
        SERVICE_SAVE_CHARGING_SCHEDULE,
        SERVICE_VERIFY_COMMAND_ACCESS,
    ):
        hass.services.async_remove(DOMAIN, service)
