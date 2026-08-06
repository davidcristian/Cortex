"""Offer the screen only while the model that would read it can see (ADR-0029)."""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.errors import ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.screen_tool import CAPTURE_SCREEN_TOOL_NAME
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

# What the model reads when it calls the screen and the model serving cannot read pictures. It
# names the reason rather than saying "unknown tool", because the tool is not unknown: it exists
# and is useless right now, and a model told that can answer from what it already has.
BLIND_MSG = (
    f"{CAPTURE_SCREEN_TOOL_NAME!r} is unavailable: the model now serving cannot read images, so "
    "the screen was not read"
)


class VisionProbe(Protocol):
    """Whether the model serving this tier right now can read a picture (ADR-0029)."""

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
        """Delegate every other call; refuse a capture the serving model could not read."""
        if call.name == CAPTURE_SCREEN_TOOL_NAME and not await self._probe.can_see():
            raise ToolNotFoundError(BLIND_MSG)
        return await self._inner.invoke(call)
