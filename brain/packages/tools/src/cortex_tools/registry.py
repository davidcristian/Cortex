"""McpToolRegistry: the core's ToolRegistry port over an MCP server (ADR-0009).

A thin translator between the core's tool values and the MCP client SDK: `describe_tools`
lists the server's tools, `invoke` calls one and renders its text content back. It holds no
state (the one hard rule) beyond the injected `McpSession`. Every transport/protocol failure
crosses the port as `ToolError` with the cause chained; a tool that ran but reported an error
comes back as an ``is_error`` `ToolResult` (the dispatcher audits it, the model recovers).

Sessions are opened per call via `streamable_http_session` (a structured, *same-task*
``async with``) and driven by `ReconnectingMcpToolRegistry` (ADR-0009 boot-tolerance
addendum). That replaces holding a session on a long-lived ``AsyncExitStack``, whose anyio
task-group cancel scopes cannot be exited from a different task (the source of the boot-time
``CancelledError`` the old eager wiring hit); the per-call open also makes a sidecar down at
boot tolerable and a recovered one rejoin without a restart.

Coverage without a server: the adapter talks to the injected `McpSession` port (the slice of
`mcp.ClientSession` it uses), which the real session satisfies in production and a fake
satisfies in CI (the MCP analog of the accepted MockTransport pattern). The behavioral
contract against a real MCP server is the integration-marked `test_registry_live.py`.
"""

from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ListToolsResult, TextContent

from cortex_core import ToolCall, ToolError, ToolResult, ToolSpec

# McpError covers protocol-level failures; OSError covers socket-level transport failures.
# Both cross the ToolRegistry port as ToolError with the cause chained.
_WRAPPED = (McpError, OSError)

# Opening a session can additionally fail with an httpx transport error (a refused dial is
# httpx.ConnectError, delivered inside anyio's ExceptionGroup); `except*` unwraps the group and
# the whole set crosses the port as ToolError so an outer SkipUnavailableToolRegistry can serve
# around a dead sidecar (ADR-0009 boot-tolerance addendum).
_OPEN_WRAPPED = (McpError, OSError, httpx.HTTPError)


class McpSession(Protocol):
    """The slice of ``mcp.ClientSession`` the adapter uses; the real session and a fake match it."""

    async def list_tools(self) -> ListToolsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...


@asynccontextmanager
async def streamable_http_session(url: str) -> AsyncGenerator[McpSession, None]:
    """Open a structured, same-task streamable-http MCP session at ``url`` (ADR-0009).

    Unlike a session held on a long-lived ``AsyncExitStack`` (whose anyio task-group cancel
    scopes cannot be exited from a different task, which is the source of the boot-time
    ``CancelledError`` the eager wiring hit), this opens and closes the session inside one
    ``async with`` in the caller's task, so a refused dial surfaces as a clean, catchable
    error. Real network I/O is driven by `ReconnectingMcpToolRegistry` and exercised for real only
    by the host-only live test.
    """
    async with (
        streamable_http_client(url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


class McpToolRegistry:
    """ToolRegistry adapter over an MCP server reached through an `McpSession` (ADR-0009)."""

    def __init__(self, session: McpSession) -> None:
        self._session = session

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


class ReconnectingMcpToolRegistry:
    """A ``ToolRegistry`` that opens a fresh MCP session per call (ADR-0009 boot tolerance).

    The composition root no longer dials at startup; this dials on demand from an injected
    ``opener``, a same-task session context manager (`streamable_http_session` in production).
    Two properties fall out: a sidecar **down at boot is tolerated** (the first call's open
    fails as ``ToolError``, which an outer `SkipUnavailableToolRegistry` reports and serves
    around) and a **recovered sidecar rejoins without a brain restart** (the next call re-dials).

    An open failure (`_OPEN_WRAPPED`, unwrapped from anyio's ``ExceptionGroup`` by ``except*``)
    crosses the port as ``ToolError`` with the cause chained; a failure from the live session's
    own ``describe``/``invoke`` is already a ``ToolError`` (`McpToolRegistry`) and passes
    through untouched. Holds no session between calls, so nothing to close, no cross-task state
    (the one hard rule). It trades a per-call open for that robustness; a session cache is a
    later optimization behind this same port.
    """

    def __init__(self, opener: Callable[[], AbstractAsyncContextManager[McpSession]]) -> None:
        self._opener = opener

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """Open a session and list its tools; an unavailable sidecar surfaces as ``ToolError``."""
        async with self._connected() as registry:
            return await registry.describe_tools()

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Open a session and call one tool; an unavailable sidecar surfaces as ``ToolError``."""
        async with self._connected() as registry:
            return await registry.invoke(call)

    @asynccontextmanager
    async def _connected(self) -> AsyncGenerator[McpToolRegistry, None]:
        """Yield an `McpToolRegistry` over a freshly opened session, mapping open failures.

        The ``except*`` unwraps anyio's ``ExceptionGroup`` and maps a dial/open failure to
        ``ToolError``; a ``ToolError`` the yielded body raises is not in ``_OPEN_WRAPPED``, so
        it propagates untouched (no double-wrap of `McpToolRegistry`'s own listing/call error).
        """
        try:
            async with self._opener() as session:
                yield McpToolRegistry(session)
        except* _OPEN_WRAPPED as group:
            msg = "MCP sidecar unavailable"
            raise ToolError(msg) from group
