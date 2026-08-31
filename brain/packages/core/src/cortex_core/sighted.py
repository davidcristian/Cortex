"""Offer the screen only while the model that would read it can see."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.errors import ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.screen_tool import CAPTURE_SCREEN_TOOL_NAME
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

BLIND_MSG = (
    f"{CAPTURE_SCREEN_TOOL_NAME!r} is unavailable: the model now serving cannot read images, so "
    "the screen was not read"
)


class VisionProbe(Protocol):
    """Whether the model serving this tier right now can read a picture."""

    async def can_see(self) -> bool: ...


class SightedToolRegistry:
    """A ``ToolRegistry`` offering ``capture_screen`` only while the serving model can see."""

    def __init__(self, inner: ToolRegistry, probe: VisionProbe) -> None:
        self._inner = inner
        self._probe = probe

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, minus the screen when the model cannot read one."""
        specs = await self._inner.describe_tools()
        if not any(spec.name == CAPTURE_SCREEN_TOOL_NAME for spec in specs):
            return specs
        if await self._probe.can_see():
            return specs
        return tuple(spec for spec in specs if spec.name != CAPTURE_SCREEN_TOOL_NAME)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate every other call; raise for a capture the serving model could not read."""
        if call.name == CAPTURE_SCREEN_TOOL_NAME and not await self._probe.can_see():
            raise ToolNotFoundError(BLIND_MSG)
        return await self._inner.invoke(call)
