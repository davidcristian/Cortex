"""McpToolRegistry: the core's ToolRegistry port over an MCP server (ADR-0009).

A thin translator between the core's tool values and the MCP client SDK: `describe_tools`
lists the server's tools, `invoke` calls one and renders its text content back. It holds no
state (the one hard rule) beyond the injected `McpSession`. Every transport or protocol
failure crosses the port as `ToolError` with the cause chained; a tool that ran but reported
an error comes back as an ``is_error`` `ToolResult`.

Sessions are opened per call by `ReconnectingMcpToolRegistry` (ADR-0009 boot-tolerance
addendum), because a session held on a long-lived ``AsyncExitStack`` cannot be exited from a
different task than opened it: anyio's task-group cancel scopes raised ``CancelledError`` at
boot under the old eager wiring. docs/modules/brain-tools.md states the rest of the contract.
"""

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol, cast

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ListToolsResult, TextContent

from cortex_core import Provenance, ToolCall, ToolError, ToolResult, ToolSpec, claimed_source

# The MCP result `_meta` key a sidecar declares a content source under (ADR-0027/0009). It rides
# beside the readable content blocks, so a declaration never disturbs the string the model consumes
# (unlike `structuredContent`). The key is a wire contract because a sidecar cannot import the
# core, the standalone email server being one; the core's `claimed_source` admits only a claimed
# SENDER/URI and sanitizes its value.
_SOURCE_META_KEY = "cortex/source"

# The two field names a declaration is written under, the kind word and the value. Bound here and
# again in the email sidecar for the reason the key is: a field renamed on one side alone would
# read as no declaration, and `crosscheck.py` holds each pair of bindings equal.
_KIND_FIELD = "kind"
_VALUE_FIELD = "value"

# McpError covers protocol-level failures; OSError covers socket-level transport failures.
# Both cross the ToolRegistry port as ToolError with the cause chained.
_WRAPPED = (McpError, OSError)

# Opening a session can additionally fail with an httpx transport error (a refused dial is
# httpx.ConnectError, delivered inside anyio's ExceptionGroup); `except*` unwraps the group and
# the whole set crosses the port as ToolError so an outer SkipUnavailableToolRegistry can serve
# around a dead sidecar (ADR-0009 boot-tolerance addendum).
_OPEN_WRAPPED = (McpError, OSError, httpx.HTTPError)


def _declared_source(result: CallToolResult) -> Provenance | None:
    """The source a sidecar declared for this result, as a claimed ``Provenance`` (ADR-0027/0009).

    Read from the result's MCP ``_meta`` side channel. ``claimed_source`` returns ``None`` for a
    malformed or absent declaration, and for one naming an attested kind a hostile sidecar might
    forge; only a sanitized, bounded, claimed SENDER/URI passes.
    """
    meta: Mapping[str, object] = result.meta or {}
    declaration = meta.get(_SOURCE_META_KEY)
    if not isinstance(declaration, Mapping):
        return None
    fields = cast("Mapping[str, object]", declaration)
    return claimed_source(fields.get(_KIND_FIELD), fields.get(_VALUE_FIELD))


class McpSession(Protocol):
    """The slice of ``mcp.ClientSession`` the adapter uses; the real session and a fake match it."""

    async def list_tools(self) -> ListToolsResult: ...

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult: ...


@asynccontextmanager
async def streamable_http_session(url: str) -> AsyncGenerator[McpSession, None]:
    """Open a structured, same-task streamable-http MCP session at ``url`` (ADR-0009).

    The session opens and closes inside one ``async with`` in the caller's task, so a refused
    dial surfaces as a catchable error rather than the boot-time ``CancelledError`` a session
    held across tasks produced. Only the host-only live test exercises the real network I/O.
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
        """Call one MCP tool; return its rendered text content, ``is_error`` set on failure.

        A source the sidecar declared in the result's ``_meta`` (``_declared_source``) rides in as
        ``ToolResult.source``, read from beside the content blocks so it never touches the text.
        """
        try:
            result = await self._session.call_tool(call.name, dict(call.arguments))
        except _WRAPPED as err:
            msg = f"MCP tool {call.name!r} failed"
            raise ToolError(msg) from err
        text = "".join(block.text for block in result.content if isinstance(block, TextContent))
        return ToolResult(
            call_id=call.id,
            content=text,
            is_error=bool(result.isError),
            source=_declared_source(result),
        )


class ReconnectingMcpToolRegistry:
    """A ``ToolRegistry`` that opens a fresh MCP session per call (ADR-0009 boot tolerance).

    The composition root does not dial at startup; this dials on demand from an injected
    ``opener``, a same-task session context manager (`streamable_http_session` in production).
    A sidecar down at boot is therefore tolerated, since the first call's open fails as
    ``ToolError`` for an outer `SkipUnavailableToolRegistry` to serve around, and a recovered
    sidecar rejoins on the next call without a brain restart.

    An open failure (`_OPEN_WRAPPED`, unwrapped from anyio's ``ExceptionGroup`` by ``except*``)
    crosses the port as ``ToolError`` with the cause chained; a failure from the live session's
    own ``describe``/``invoke`` is already a ``ToolError`` and passes through untouched. No
    session is held between calls, so there is nothing to close and no cross-task state. The
    cost is one open per call; a session cache would go behind this same port.
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
