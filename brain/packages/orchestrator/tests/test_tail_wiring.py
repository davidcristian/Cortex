from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

import cortex_orchestrator.builders as builders_module
from cortex_core import ToolCall
from cortex_orchestrator.builders import build_tool_registry
from cortex_orchestrator.config_tools import ToolsConfig

_URL = "http://mcp-filesystem:9000/mcp"
_READS = ("read_text_file", "read_file")


class _TailSession:
    """A filesystem server whose ``tail`` counts the empty text after a final newline as a line."""

    def __init__(self, sent: list[dict[str, object]]) -> None:
        self._sent = sent

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[Tool(name=name, description="", inputSchema={}) for name in _READS]
        )

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        del name
        args = arguments or {}
        self._sent.append(args)
        count = args["tail"]
        assert isinstance(count, int)
        text = "\n".join(["first", "second", "the last line", ""][-count:])
        return CallToolResult(content=[TextContent(type="text", text=text)], isError=False)


async def test_a_built_registry_reads_the_real_last_line_of_a_filesystem_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, object]] = []

    @asynccontextmanager
    async def opener(url: str) -> AsyncGenerator[_TailSession, None]:
        del url
        yield _TailSession(sent)

    monkeypatch.setattr(builders_module, "streamable_http_session", opener)
    registry, close = build_tool_registry(
        ToolsConfig(backend="mcp", endpoints={"filesystem": _URL})
    )
    assert registry is not None
    for name in _READS:
        call = ToolCall(id="c1", name=name, arguments={"path": "/projects/a.log", "tail": 1})
        assert (await registry.invoke(call)).content == "the last line"
    assert [args["tail"] for args in sent] == [2, 2]
    await close()
