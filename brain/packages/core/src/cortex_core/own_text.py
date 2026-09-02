"""The own-text overlay: marks a remote result trusted when its text is text the brain wrote."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

# Returns None when the call's arguments do not fit the renderer, so nothing matches and the
# result stays untrusted.
type OwnTextRenderer = Callable[[Mapping[str, Any]], str | None]


@dataclass(frozen=True, slots=True)
class OwnText:
    """One text the brain holds for one tool, rendered from the call's own arguments."""

    tool: str
    render: OwnTextRenderer


class OwnTextToolRegistry:
    """A ``ToolRegistry`` that marks a result ``TRUSTED`` when its text is the brain's own."""

    def __init__(self, inner: ToolRegistry, *, own: Sequence[OwnText]) -> None:
        if not own:
            msg = "OwnTextToolRegistry needs a non-empty own-text set"
            raise ValueError(msg)
        self._inner = inner
        by_tool: dict[str, tuple[OwnText, ...]] = {}
        for text in own:
            by_tool[text.tool] = (*by_tool.get(text.tool, ()), text)
        self._own = by_tool

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """Delegate unchanged: this overlay changes results, never the advertised tools."""
        return await self._inner.describe_tools()

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate, then mark the result trusted only when it is one of the brain's own texts."""
        result = await self._inner.invoke(call)
        if result.images:
            return result
        for text in self._own.get(call.name, ()):
            if text.render(call.arguments) == result.content:
                return replace(result, trust=Trust.TRUSTED)
        return result
