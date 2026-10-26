"""How long a listing or call on a remote tool server may take, and what follows an overrun."""

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

if TYPE_CHECKING:
    from datetime import datetime

# Far above a healthy call: the shipped filesystem sidecar answers an invoke in 154 ms and a
# listing in 146 ms (the table in docs/runbooks/tools-mcp.md).
DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0
DEFAULT_TOOL_LIST_TIMEOUT_S = 10.0
DEFAULT_TOOL_RETRY_AFTER_S = 120.0

LISTING_OVERRAN_MSG = (
    "the {server} tool server did not list its tools within {timeout_s:g}s, "
    "so they are not listed again for {retry_s:g}s"
)
CALL_OVERRAN_MSG = (
    "the {server} tool server did not answer {name!r} within {timeout_s:g}s, so the call did not "
    "finish; its tools fail at once for the next {retry_s:g}s, so answer without them"
)
RESTING_LIST_MSG = (
    "the {server} tool server did not answer in time earlier, "
    "so its tools are not listed for another {left:.0f}s"
)
RESTING_CALL_MSG = (
    "the {server} tool server did not answer in time earlier, so {name!r} was not sent; "
    "its tools fail at once for another {left:.0f}s, so answer without them"
)


class BoundedToolRegistry:
    """A ``ToolRegistry`` whose calls give up after a bound, and that rests a server that overran.

    After an overrun every listing and call fails at once until ``retry_after_s`` has passed.
    """

    def __init__(
        self,
        inner: ToolRegistry,
        *,
        server: str,
        clock: Clock,
        timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S,
        list_timeout_s: float = DEFAULT_TOOL_LIST_TIMEOUT_S,
        retry_after_s: float = DEFAULT_TOOL_RETRY_AFTER_S,
    ) -> None:
        for value in (timeout_s, list_timeout_s, retry_after_s):
            if value <= 0:
                msg = f"BoundedToolRegistry needs a positive bound, got {value}"
                raise ValueError(msg)
        self._inner = inner
        self._server = server
        self._clock = clock
        self._timeout_s = timeout_s
        # Never above the call bound, so pricing every walk at the call bound stays an upper bound.
        self._list_timeout_s = min(list_timeout_s, timeout_s)
        self._retry_after_s = retry_after_s
        self._overran_at: datetime | None = None

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools; an overrun, or a listing while resting, raises ToolError."""
        left = self._rest_left()
        if left is not None:
            raise ToolError(RESTING_LIST_MSG.format(server=self._server, left=left))
        bound = asyncio.timeout(self._list_timeout_s)
        try:
            async with bound:
                return await self._inner.describe_tools()
        except TimeoutError as err:
            if not bound.expired():
                raise
            self._overran_at = self._clock.now()
            msg = LISTING_OVERRAN_MSG.format(
                server=self._server, timeout_s=self._list_timeout_s, retry_s=self._retry_after_s
            )
            raise ToolError(msg) from err

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate one call; an overrun is cancelled, and a call while resting is never sent."""
        left = self._rest_left()
        if left is not None:
            raise ToolError(RESTING_CALL_MSG.format(server=self._server, name=call.name, left=left))
        bound = asyncio.timeout(self._timeout_s)
        try:
            async with bound:
                return await self._inner.invoke(call)
        except TimeoutError as err:
            if not bound.expired():
                raise
            self._overran_at = self._clock.now()
            msg = CALL_OVERRAN_MSG.format(
                server=self._server,
                name=call.name,
                timeout_s=self._timeout_s,
                retry_s=self._retry_after_s,
            )
            raise ToolError(msg) from err

    def _rest_left(self) -> float | None:
        """Seconds left of the rest after the last overrun, or None when the server may be used."""
        if self._overran_at is None:
            return None
        elapsed = (self._clock.now() - self._overran_at).total_seconds()
        # A clock set back makes the elapsed time negative, which ends the rest rather than
        # lengthening it.
        if 0 <= elapsed < self._retry_after_s:
            return self._retry_after_s - elapsed
        return None
