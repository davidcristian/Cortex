"""Read a file's last lines from a server whose ``tail`` counts a final newline as a line."""

from collections.abc import Sequence
from dataclasses import replace

from cortex_core.ports_tools import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

TAIL_ARGUMENT = "tail"


# The reference filesystem server, through 2.0.1, returns the empty text after a final newline as
# the file's last line, so its ``tail`` 1 of almost any text file is empty.
class LastLinesToolRegistry:
    """A ``ToolRegistry`` that reads a ``tail`` from the named tools without the empty line."""

    def __init__(self, inner: ToolRegistry, *, tools: Sequence[str]) -> None:
        self._inner = inner
        self._tools = frozenset(tools)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, unchanged."""
        return await self._inner.describe_tools()

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Run ``call``; a ``tail`` read of a named tool returns the file's real last lines."""
        count = call.arguments.get(TAIL_ARGUMENT)
        if call.name not in self._tools or type(count) is not int or count < 1:
            return await self._inner.invoke(call)
        wider = replace(call, arguments={**call.arguments, TAIL_ARGUMENT: count + 1})
        result = await self._inner.invoke(wider)
        if result.is_error:
            return result
        lines = result.content.split("\n")
        if lines[-1] == "":
            lines.pop()
        return replace(result, content="\n".join(lines[-count:]))
