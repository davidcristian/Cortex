"""McpToolRegistry: the core's ToolRegistry port over an MCP server (ADR-0009).

A thin translator between the core's tool values and the MCP client SDK: `describe_tools`
lists the server's tools, `invoke` calls one and renders its text content back. It holds no
state (the one hard rule) beyond the injected `McpSession`. Every transport/protocol failure
crosses the port as `ToolError` with the cause chained; a tool that ran but reported an error
comes back as an ``is_error`` `ToolResult` (the dispatcher audits it, the model recovers).

Coverage without a server: the adapter talks to the injected `McpSession` port (the slice of
`mcp.ClientSession` it uses), which the real session satisfies in production and a fake
satisfies in CI (the MCP analog of the accepted MockTransport pattern). The behavioral
contract against a real MCP server is the integration-marked `test_registry_live.py`.
"""

from collections.abc import Awaitable, Callable, Sequence
from contextlib import AsyncExitStack
from typing import Protocol

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ListToolsResult, TextContent

from cortex_core import ToolCall, ToolError, ToolResult, ToolSpec

# McpError covers protocol-level failures; OSError covers socket-level transport failures.
# Both cross the ToolRegistry port as ToolError with the cause chained.
_WRAPPED = (McpError, OSError)


class McpSession(Protocol):
    """The slice of ``mcp.ClientSession`` the adapter uses; the real session and a fake match it."""

    async def list_tools(self) -> ListToolsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...


class McpToolRegistry:
    """ToolRegistry adapter over an MCP server reached through an `McpSession` (ADR-0009)."""

    def __init__(self, session: McpSession) -> None:
        self._session = session

    @classmethod
    async def connect(cls, url: str) -> tuple["McpToolRegistry", Callable[[], Awaitable[None]]]:
        """Open a streamable-http MCP session at ``url``; return the registry and its closer.

        The transport and session are held open on an ``AsyncExitStack`` for the app's
        lifetime; the returned closer unwinds it at composition-root shutdown. Real network
        I/O (exercised only by the host-only live test, never in CI).
        """
        stack = AsyncExitStack()
        read, write, _ = await stack.enter_async_context(streamable_http_client(url))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return cls(session), stack.aclose

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """List the MCP server's tools as `ToolSpec`s to advertise to the model."""
        try:
            result = await self._session.list_tools()
        except _WRAPPED as err:
            msg = "listing MCP tools failed"
            raise ToolError(msg) from err
        return [
            ToolSpec(
                name=tool.name, description=tool.description or "", parameters=tool.inputSchema
            )
            for tool in result.tools
        ]

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Call one MCP tool; return its rendered text content, ``is_error`` set on failure."""
        try:
            result = await self._session.call_tool(call.name, dict(call.arguments))
        except _WRAPPED as err:
            msg = f"MCP tool {call.name!r} failed"
            raise ToolError(msg) from err
        text = "".join(block.text for block in result.content if isinstance(block, TextContent))
        return ToolResult(call_id=call.id, content=text, is_error=bool(result.isError))
