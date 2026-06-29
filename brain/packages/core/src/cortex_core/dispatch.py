"""Dispatch one tool call and audit it. It is the only path a tool runs through (ADR-0009)."""

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, ToolAuditSink, ToolRegistry
from cortex_core.tools import ToolCall, ToolInvocation, ToolResult


class ToolDispatcher:
    """Run a tool call through the registry, recording one audit line per dispatch."""

    def __init__(self, registry: ToolRegistry, audit: ToolAuditSink, clock: Clock) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock

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
