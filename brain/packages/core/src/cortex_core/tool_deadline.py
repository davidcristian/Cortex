"""How long one call on a remote tool server may take, and what an overrun is reported as."""

import asyncio
from collections.abc import Sequence

from cortex_core.errors import ToolError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

# Far above a healthy call: the shipped filesystem sidecar answers an invoke in 154 ms and a
# listing in 146 ms (the table in docs/runbooks/tools-mcp.md). It bounds one call, not a turn,
# so a wedged sidecar can cost a loop several of these.
DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0

LISTING_OVERRAN_MSG = "listing a tool sidecar's tools took longer than {timeout_s:g}s"
CALL_OVERRAN_MSG = "tool {name!r} did not answer within {timeout_s:g}s"


class BoundedToolRegistry:
    """A ``ToolRegistry`` whose every call gives up after ``timeout_s``."""

    def __init__(
        self, inner: ToolRegistry, *, timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S
    ) -> None:
        if timeout_s <= 0:
            msg = f"BoundedToolRegistry needs a positive bound, got {timeout_s}"
            raise ValueError(msg)
        self._inner = inner
        self._timeout_s = timeout_s

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools; a listing that outruns the bound raises ``ToolError``."""
        bound = asyncio.timeout(self._timeout_s)
        try:
            async with bound:
                return await self._inner.describe_tools()
        except TimeoutError as err:
            if not bound.expired():
                raise
            msg = LISTING_OVERRAN_MSG.format(timeout_s=self._timeout_s)
            raise ToolError(msg) from err

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate one call; one that outruns the bound is cancelled and raises ``ToolError``."""
        bound = asyncio.timeout(self._timeout_s)
        try:
            async with bound:
                return await self._inner.invoke(call)
        except TimeoutError as err:
            if not bound.expired():
                raise
            msg = CALL_OVERRAN_MSG.format(name=call.name, timeout_s=self._timeout_s)
            raise ToolError(msg) from err
