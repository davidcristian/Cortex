"""The own-text overlay: a remote result re-stamped trusted on bytes the brain holds (ADR-0013).

``McpToolRegistry`` leaves every result at the fail-closed ``Trust.UNTRUSTED`` default, which is
right for mail and file contents. A few answers a sidecar composes without reading anything, the
email sidecar's two refusals and its two empty results, carry only text this repo wrote plus the
argument the model put on the call; fenced and tainting, they close the turn's outbound surface
and put a correction inside the region the preamble says never to obey. This overlay re-stamps
exactly those, under one rule (ADR-0013 own-text addendum): a result is ``Trust.TRUSTED`` only
when its whole ``content`` is byte-equal to the text one ``OwnText`` renders from the call's own
arguments and it carries no image. Nothing the wire says takes part: ``is_error`` is not read,
the declared ``source`` is not read, and a sidecar that changes one byte of its wording lands
on the tainting side, which is the safe one. Pure routing over the port, with no I/O and no
state (the one hard rule).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

# The expected text for one call, or ``None`` when the call's arguments do not fit the renderer
# (a field missing or not a string), so nothing matches and the result stays untrusted.
type OwnTextRenderer = Callable[[Mapping[str, Any]], str | None]


@dataclass(frozen=True, slots=True)
class OwnText:
    """One text the brain holds for one tool, rendered from the call's own arguments.

    ``render`` returns the exact string the tool answers with for those arguments. A literal
    answer ignores them and a refusal quoting the model's argument reads it back, so both are
    declared in this one shape. The arguments are the brain's own copy of the call, never anything
    the sidecar returned.
    """

    tool: str
    render: OwnTextRenderer


class OwnTextToolRegistry:
    """A ``ToolRegistry`` re-stamping a result ``TRUSTED`` when its bytes are the brain's own.

    The composition-root trust overlay for remote tools, beside ``GatedToolRegistry``:
    ``describe_tools`` delegates untouched, and ``invoke`` delegates and then re-stamps the result
    exactly when its content equals what one declared ``OwnText`` for the called tool renders
    from the call's arguments and the result carries no image. Every other result passes through
    unchanged, ``is_error`` and ``source`` included. Keyed by tool name, since the root does not
    know which endpoint serves a sidecar and the bytes are the fact either way. An empty
    declaration set is rejected, because an overlay declaring nothing would only look like one.
    """

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
        """Delegate untouched: the overlay changes what a result is, never what is advertised."""
        return await self._inner.describe_tools()

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate, then re-stamp the result trusted only when it is one of the brain's own texts.

        The expected text is rendered from ``call.arguments``, the brain's own copy, so a sidecar
        echoing some other argument back does not match. An image is never the brain's own, so a
        result carrying one is left alone before any text is compared.
        """
        result = await self._inner.invoke(call)
        if result.images:
            return result
        for text in self._own.get(call.name, ()):
            if text.render(call.arguments) == result.content:
                return replace(result, trust=Trust.TRUSTED)
        return result
