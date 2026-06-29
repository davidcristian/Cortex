"""Behavior tests for McpToolRegistry over a fake McpSession (no server, no network).

The fake returns real ``mcp`` result types, so the mapping is proven against the SDK's
actual shapes; the behavioral contract against a live MCP server is test_registry_live.py.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Self

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import (
    CallToolResult,
    ErrorData,
    ImageContent,
    ListToolsResult,
    TextContent,
    Tool,
)

import cortex_tools.registry as registry_module
from cortex_core import ToolCall, ToolError, ToolResult
from cortex_tools import McpToolRegistry


class FakeSession:
    """A fake McpSession returning canned results, or raising, for the mapping tests."""

    def __init__(
        self,
        *,
        tools: ListToolsResult | None = None,
        result: CallToolResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._tools = tools
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def list_tools(self) -> ListToolsResult:
        if self._error is not None:
            raise self._error
        assert self._tools is not None
        return self._tools

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        self.calls.append((name, arguments))
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def test_describe_tools_maps_server_tools_to_specs() -> None:
    tools = ListToolsResult(
        tools=[
            Tool(name="read", description="read a file", inputSchema={"type": "object"}),
            Tool(name="list", description=None, inputSchema={"type": "object"}),
        ]
    )
    specs = await McpToolRegistry(FakeSession(tools=tools)).describe_tools()
    assert [(s.name, s.description) for s in specs] == [("read", "read a file"), ("list", "")]
    assert specs[0].parameters == {"type": "object"}


async def test_invoke_renders_text_content_and_skips_non_text() -> None:
    result = CallToolResult(
        content=[
            TextContent(type="text", text="line1\n"),
            ImageContent(type="image", data="ignored", mimeType="image/png"),
            TextContent(type="text", text="line2"),
        ],
        isError=False,
    )
    session = FakeSession(result=result)
    out = await McpToolRegistry(session).invoke(
        ToolCall(id="c1", name="read", arguments={"path": "/etc/hosts"})
    )
    assert out == ToolResult(call_id="c1", content="line1\nline2", is_error=False)
    assert session.calls == [("read", {"path": "/etc/hosts"})]


async def test_invoke_marks_a_tool_reported_error() -> None:
    result = CallToolResult(content=[TextContent(type="text", text="ENOENT")], isError=True)
    out = await McpToolRegistry(FakeSession(result=result)).invoke(
        ToolCall(id="c2", name="read", arguments={})
    )
    assert out == ToolResult(call_id="c2", content="ENOENT", is_error=True)


async def test_invoke_wraps_transport_failure_as_tool_error() -> None:
    err = McpError(ErrorData(code=-32603, message="server exploded"))
    registry = McpToolRegistry(FakeSession(error=err))
    with pytest.raises(ToolError, match=r"MCP tool 'read' failed") as excinfo:
        await registry.invoke(ToolCall(id="c3", name="read", arguments={}))
    assert isinstance(excinfo.value.__cause__, McpError)


async def test_describe_tools_wraps_transport_failure_as_tool_error() -> None:
    registry = McpToolRegistry(FakeSession(error=OSError("no route to host")))
    with pytest.raises(ToolError, match="listing MCP tools failed") as excinfo:
        await registry.describe_tools()
    assert isinstance(excinfo.value.__cause__, OSError)


async def test_connect_opens_a_session_initializes_it_and_returns_a_closer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_url: list[str] = []
    lifecycle: list[str] = []

    @asynccontextmanager
    async def fake_streamable(url: str) -> AsyncGenerator[tuple[str, str, object], None]:
        seen_url.append(url)
        yield ("read", "write", lambda: None)

    class FakeConnectSession:
        def __init__(self, read: object, write: object) -> None:
            self._read, self._write = read, write

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            lifecycle.append("session-closed")
            return False

        async def initialize(self) -> None:
            lifecycle.append("initialized")

        async def list_tools(self) -> ListToolsResult:
            return ListToolsResult(tools=[])

        async def call_tool(
            self, name: str, arguments: dict[str, object] | None = None
        ) -> CallToolResult:
            del name, arguments
            raise NotImplementedError

    monkeypatch.setattr(registry_module, "streamable_http_client", fake_streamable)
    monkeypatch.setattr(registry_module, "ClientSession", FakeConnectSession)
    registry, close = await McpToolRegistry.connect("http://fs:9000/mcp")
    assert isinstance(registry, McpToolRegistry)
    assert list(await registry.describe_tools()) == []  # the session is live and usable
    await close()
    assert seen_url == ["http://fs:9000/mcp"]
    assert lifecycle == ["initialized", "session-closed"]
