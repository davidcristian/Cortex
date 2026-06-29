"""Dispatch one tool call and audit it. It is the only path a tool runs through (ADR-0009).

``ToolDispatcher`` is a stateless function over the ``ToolRegistry`` + ``ToolAuditSink``
ports, like ``MemoryRecaller`` over the memory ports: it holds no state, so a restart or
model swap between calls changes nothing (the one hard rule). Its contract is that **every**
dispatch writes exactly one audit record, so a dispatch failure becomes an ``is_error``
``ToolResult`` (the model is told and can recover), never an unaudited crash.
"""

from collections.abc import Sequence

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, ToolAuditSink, ToolRegistry
from cortex_core.tools import ToolCall, ToolInvocation, ToolResult, ToolSpec


class ToolDispatcher:
    """Run a tool call through the registry, recording one audit line per dispatch.

    Also the turn's single tool gateway: ``describe_tools`` passes through to the registry
    so the engine advertises the same tools it can dispatch.
    """

    def __init__(self, registry: ToolRegistry, audit: ToolAuditSink, clock: Clock) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    async def dispatch(self, call: ToolCall) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes.

        A ``ToolError`` from the registry (unknown tool, transport) is caught and returned as
        an ``is_error`` result. The loop keeps going and the model sees the failure.
        """
        try:
            result = await self._registry.invoke(call)
        except ToolError as err:
            result = ToolResult(call_id=call.id, content=str(err), is_error=True)
        await self._audit.record(
            ToolInvocation(
                name=call.name,
                arguments=call.arguments,
                ok=not result.is_error,
                detail=result.content,
                at=self._clock.now(),
            )
        )
        return result
