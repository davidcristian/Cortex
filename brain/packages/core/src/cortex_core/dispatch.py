"""Dispatch one tool call and audit it. It is the only path a tool runs through (ADR-0009/0013).

``ToolDispatcher`` is a stateless function over the ``ToolRegistry`` + ``ToolAuditSink``
ports, like ``MemoryRecaller`` over the memory ports: it holds no state, so a restart or
model swap between calls changes nothing (the one hard rule). Its contract is that **every**
dispatch writes exactly one audit record, so a dispatch failure becomes an ``is_error``
``ToolResult`` (the model is told and can recover), never an unaudited crash.

It is also the capability gate (ADR-0013): a ``gated`` (irreversible/outbound) tool called on
a turn that has read untrusted content (``tainted``) must be confirmed by the ``Confirmer``
before it runs. A denial (including the fail-closed no-confirmer default) returns the
``DENIED_MSG`` error result **without invoking the tool**, and audits the block. The
confirmation is the human's, reached out of band, never the (possibly jailbroken) model's.
"""

from collections.abc import Sequence

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
from cortex_core.tools import (
    ConfirmationRequest,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    Trust,
)
from cortex_core.untrusted import DENIED_MSG

# Why a gated call was stopped, shown to the user by the overlay confirmer (ADR-0013).
_GATE_REASON = "outbound or irreversible action requested after this turn read untrusted content"


class ToolDispatcher:
    """Run a tool call through the registry, gating and recording one audit line per dispatch.

    Also the turn's single tool gateway: ``describe_tools`` passes through to the registry
    so the engine advertises the same tools it can dispatch.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        audit: ToolAuditSink,
        clock: Clock,
        *,
        confirmer: Confirmer | None = None,
    ) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock
        self._confirmer = confirmer

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    async def dispatch(
        self, call: ToolCall, *, tainted: bool = False, gated: bool = False
    ) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes.

        A gated tool on a tainted turn is confirmed first; a denial returns ``DENIED_MSG``
        without invoking the tool. Otherwise a ``ToolError`` from the registry (unknown tool,
        transport) is caught and returned as an ``is_error`` result. The loop keeps going and
        the model sees the failure.
        """
        if gated and tainted and not await self._confirmed(call):
            blocked = ToolResult(
                call_id=call.id, content=DENIED_MSG, is_error=True, trust=Trust.TRUSTED
            )
            return await self._audited(call, blocked)
        try:
            result = await self._registry.invoke(call)
        except ToolError as err:
            # Our own dispatch-error message (not external content) is trusted, so it neither
            # frames as data nor taints the turn.
            result = ToolResult(
                call_id=call.id, content=str(err), is_error=True, trust=Trust.TRUSTED
            )
        return await self._audited(call, result)

    async def _confirmed(self, call: ToolCall) -> bool:
        """Ask the confirmer to approve a gated call; a missing confirmer denies (fail-closed)."""
        if self._confirmer is None:
            return False
        request = ConfirmationRequest(
            tool_name=call.name, arguments=call.arguments, reason=_GATE_REASON
        )
        return await self._confirmer.confirm(request)

    async def _audited(self, call: ToolCall, result: ToolResult) -> ToolResult:
        """Record one audit line (with the result's provenance) and return the result."""
        await self._audit.record(
            ToolInvocation(
                name=call.name,
                arguments=call.arguments,
                ok=not result.is_error,
                detail=result.content,
                at=self._clock.now(),
                trust=result.trust,
            )
        )
        return result
