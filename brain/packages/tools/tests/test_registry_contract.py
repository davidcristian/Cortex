"""Every `ToolRegistry` implementation against the same checks (`registry_contract.py`).

Four arms: the core's `InMemoryToolRegistry`, the `McpToolRegistry` that does the translating,
the `ReconnectingMcpToolRegistry` production actually wires, which opens a fresh session per
call, and that one under the `BoundedToolRegistry` the composition root wraps it in. The three MCP
arms run over a serving `McpSession` that answers real ``mcp`` result types, so
only the socket is missing: the adapter's spec mapping, argument passing, text rendering,
``is_error`` reading and failure wrapping are all exercised by the same six checks the fake
passes. A stand-in server is the right fake here, because the adapter's whole job is translating
between the two shapes.

The live half against a real filesystem MCP server is `test_registry_live.py`, integration-marked
per AGENTS.md gate 3.
"""

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import partial
from typing import Any

import pytest
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ErrorData, ListToolsResult, TextContent, Tool
from registry_contract import ALL_CHECKS, Check, RegistryUnderTest, ServedTool

from cortex_core import (
    BoundedToolRegistry,
    InMemoryToolRegistry,
    ToolCall,
    ToolError,
    ToolResult,
    ToolSpec,
)
from cortex_tools import McpSession, McpToolRegistry, ReconnectingMcpToolRegistry

type Build = Callable[[], RegistryUnderTest]


class ServingSession:
    """An `McpSession` standing in for a running MCP server, tools and all.

    It answers what a real server answers: an unknown tool comes back as an error result, which is
    the SDK's own shape for it, rather than as a raise. A broken server fails both verbs at the
    transport, `McpError` on the listing and `OSError` on the call, so both of the adapter's
    wrapping sites are walked.
    """

    def __init__(self) -> None:
        self._tools: list[ServedTool] = []
        self._broken = False

    def serve(self, tools: Sequence[ServedTool]) -> None:
        self._tools = list(tools)

    def break_backend(self) -> None:
        self._broken = True

    def _find(self, name: str) -> ServedTool | None:
        return next((tool for tool in self._tools if tool.spec.name == name), None)

    async def list_tools(self) -> ListToolsResult:
        if self._broken:
            raise McpError(ErrorData(code=-32603, message="server gone"))
        return ListToolsResult(
            tools=[
                Tool(
                    name=tool.spec.name,
                    description=tool.spec.description or None,
                    inputSchema=dict(tool.spec.parameters),
                )
                for tool in self._tools
            ]
        )

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        if self._broken:
            msg = "no route to host"
            raise OSError(msg)
        tool = self._find(name)
        if tool is None:
            text = f"Unknown tool: {name}"
            return CallToolResult(content=[TextContent(type="text", text=text)], isError=True)
        rendered = tool.reply(arguments or {})
        return CallToolResult(
            content=[TextContent(type="text", text=rendered)], isError=tool.failed
        )


def _handler(tool: ServedTool) -> Callable[[Mapping[str, Any]], Any]:
    """Return the fake's handler for one served tool: its text, or a whole result when the tool
    is marked failed."""

    async def handle(arguments: Mapping[str, Any]) -> str | ToolResult:
        rendered = tool.reply(arguments)
        if tool.failed:
            return ToolResult(call_id="", content=rendered, is_error=True)
        return rendered

    return handle


def _in_memory() -> RegistryUnderTest:
    registry = InMemoryToolRegistry({})

    def serve(tools: Sequence[ServedTool]) -> None:
        registry.serve({tool.spec.name: (tool.spec, _handler(tool)) for tool in tools})

    return RegistryUnderTest(
        registry=registry,
        serve=serve,
        break_backend=lambda: registry.fail_with(ToolError("scripted registry failure")),
    )


def _over_session(*, reconnecting: bool) -> RegistryUnderTest:
    """The real adapter over a serving session, either directly or through the per-call opener."""
    session = ServingSession()

    @asynccontextmanager
    async def opener() -> AsyncGenerator[McpSession, None]:
        yield session

    registry = ReconnectingMcpToolRegistry(opener) if reconnecting else McpToolRegistry(session)
    return RegistryUnderTest(
        registry=registry, serve=session.serve, break_backend=session.break_backend
    )


def _bounded() -> RegistryUnderTest:
    """The stack production wires: the per-call opener under the bound the composition root gives
    it.

    The bound is generous rather than short, because this arm asserts that all six checks still
    hold through it. A wrapper that swallowed an unknown name, dropped a spec's schema or
    relabelled a failed tool would be invisible in the bound's own tests, which never let a call
    succeed. The overrun the bound exists for has its own suite in the core.
    """
    under_test = _over_session(reconnecting=True)
    return replace(under_test, registry=BoundedToolRegistry(under_test.registry))


_BUILDS: Sequence[tuple[str, Build]] = (
    ("in-memory", _in_memory),
    ("mcp", partial(_over_session, reconnecting=False)),
    ("reconnecting", partial(_over_session, reconnecting=True)),
    ("bounded", _bounded),
)


_ARMS = [build for _, build in _BUILDS]
_ARM_IDS = [name for name, _ in _BUILDS]


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", _ARMS, ids=_ARM_IDS)
async def test_the_contract_holds(check: Check, build: Build) -> None:
    await check(build())


def _spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description="", parameters={})


async def test_a_handler_answering_a_result_is_stamped_with_the_calls_own_id() -> None:
    # The fake's widened handler: a result a handler builds carries whatever id it likes, and the
    # registry replaces it, so a handler never has to be told which call it is serving.
    async def handle(arguments: Mapping[str, Any]) -> ToolResult:
        del arguments
        return ToolResult(call_id="not-this-one", content="ok", is_error=True)

    registry = InMemoryToolRegistry({"read": (_spec("read"), handle)})
    result = await registry.invoke(ToolCall(id="c-9", name="read", arguments={}))
    assert (result.call_id, result.content, result.is_error) == ("c-9", "ok", True)
