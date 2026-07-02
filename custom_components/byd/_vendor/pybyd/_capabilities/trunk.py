"""Trunk open/close capability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pybyd.exceptions import BydEndpointNotSupportedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class TrunkCapability:
    """Open and close the trunk remotely.

    Like :class:`FinderCapability`, these are fire-and-forget commands
    without an observable projection, so no state projections are
    registered.
    """

    def __init__(
        self,
        *,
        open_fn: Callable[..., Awaitable[Any]],
        close_fn: Callable[..., Awaitable[Any]],
        vin: str,
        execute_command: Callable[..., Awaitable[None]],
        open_available: bool | None = True,
        close_available: bool | None = True,
    ) -> None:
        self._open_fn = open_fn
        self._close_fn = close_fn
        self._vin = vin
        self._execute = execute_command
        self._open_available = open_available
        self._close_available = close_available

    @property
    def open_available(self) -> bool:
        return bool(self._open_available)

    @property
    def close_available(self) -> bool:
        return bool(self._close_available)

    async def open(self) -> None:
        """Open (release the latch of) the trunk."""
        if not self.open_available:
            raise BydEndpointNotSupportedError(
                f"Open-trunk capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="trunk.open",
            )

        async def _cmd() -> Any:
            return await self._open_fn(self._vin)

        await self._execute(_cmd, [])

    async def close(self) -> None:
        """Close (electrically lower) the trunk."""
        if not self.close_available:
            raise BydEndpointNotSupportedError(
                f"Close-trunk capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="trunk.close",
            )

        async def _cmd() -> Any:
            return await self._close_fn(self._vin)

        await self._execute(_cmd, [])
