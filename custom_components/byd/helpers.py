"""Snapshot accessors shared by the BYD platforms and coordinator.

Keeping the charging logic in one place means the ``charging`` binary sensor,
the ``charging_state`` enum sensor and the quiet-hours polling decision always
agree about whether a vehicle is charging.
"""

from __future__ import annotations

from typing import Any

from pybyd._state_engine import VehicleSnapshot
from pybyd.models.realtime import ChargingState


def rt(snapshot: VehicleSnapshot, attr: str) -> Any:
    """Read a realtime attribute, or None when the realtime section is absent."""
    realtime = snapshot.realtime
    return getattr(realtime, attr, None) if realtime is not None else None


def is_charging(snapshot: VehicleSnapshot) -> bool | None:
    """Whether the vehicle is actively charging (None when unknown).

    The BYD cloud leaves ``realtime.charging_state`` at UNKNOWN for many models
    (e.g. the Shark), so the smart-charge homepage section (``snapshot.charging``)
    is preferred: it carries the authoritative live value and is also pushed via
    MQTT. ``realtime.effective_charging_state`` (``charge_state``) is the
    fallback when that section is momentarily absent.
    """
    charging = snapshot.charging
    if charging is not None and charging.charging_state is not None:
        return charging.is_charging
    realtime = snapshot.realtime
    if realtime is not None and realtime.effective_charging_state != ChargingState.UNKNOWN:
        return realtime.effective_charging_state == ChargingState.CHARGING
    return None


def is_plugged_in(snapshot: VehicleSnapshot) -> bool | None:
    """Whether the charge cable is connected (None when unknown).

    Sourced from the smart-charge homepage (``connectState``). The realtime
    ``connect_state`` field is the T-Box link state, not the charge cable.
    """
    charging = snapshot.charging
    if charging is None or charging.connect_state is None:
        return None
    return charging.is_connected


def time_to_full_minutes(snapshot: VehicleSnapshot) -> int | None:
    """Minutes to full charge, preferring the smart-charge homepage section.

    Only ``snapshot.charging`` carries ``full_hour``/``full_minute`` for most
    models; the realtime section leaves them unset.
    """
    charging = snapshot.charging
    if charging is not None:
        minutes = charging.time_to_full_minutes
        if minutes is not None:
            return minutes
    realtime = snapshot.realtime
    return realtime.time_to_full_minutes if realtime is not None else None
