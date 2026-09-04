"""McpToolRegistry: the core's ToolRegistry port over an MCP server."""

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol, cast

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ListToolsResult, TextContent

from cortex_core import Provenance, ToolCall, ToolError, ToolResult, ToolSpec, claimed_source
from cortex_core.images import ImageError
from cortex_tools.blocks import result_images

# The result `_meta` key a sidecar declares a content source under, and the two fields the
# declaration is written with. They are a wire contract, because a sidecar cannot import the
# core, so the email server defines the same three and `crosscheck.py` compares each pair.
_SOURCE_META_KEY = "cortex/source"

_KIND_FIELD = "kind"
_VALUE_FIELD = "value"

# McpError covers protocol failures and OSError socket ones. Opening a session can also fail
# with an httpx transport error: a refused dial is httpx.ConnectError, delivered inside anyio's
# ExceptionGroup, which `except*` unwraps.
_WRAPPED = (McpError, OSError)

_OPEN_WRAPPED = (McpError, OSError, httpx.HTTPError)


def _declared_source(result: CallToolResult) -> Provenance | None:
    """The source a sidecar declared for this result, as a claimed ``Provenance``."""
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
    """Open a structured, same-task streamable-http MCP session at ``url``."""
    async with (
        streamable_http_client(url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


class McpToolRegistry:
    """ToolRegistry adapter over an MCP server reached through an `McpSession`."""

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
        """Call one MCP tool; return its text content and images, ``is_error`` set on failure."""
        try:
            result = await self._session.call_tool(call.name, dict(call.arguments))
        except _WRAPPED as err:
            msg = f"MCP tool {call.name!r} failed"
            raise ToolError(msg) from err
        text = "".join(block.text for block in result.content if isinstance(block, TextContent))
        try:
            images = result_images(result)
        except ImageError as err:
            msg = f"MCP tool {call.name!r} returned an image the adapter cannot read"
            raise ToolError(msg) from err
        return ToolResult(
            call_id=call.id,
            content=text,
            is_error=bool(result.isError),
            source=_declared_source(result),
            images=images,
        )


class ReconnectingMcpToolRegistry:
    """A ``ToolRegistry`` that opens a fresh MCP session per call, so a sidecar may boot late."""

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
        """Yield an `McpToolRegistry` over a freshly opened session, mapping open failures."""
        try:
            async with self._opener() as session:
                yield McpToolRegistry(session)
        except* _OPEN_WRAPPED as group:
            msg = "MCP sidecar unavailable"
            raise ToolError(msg) from group
