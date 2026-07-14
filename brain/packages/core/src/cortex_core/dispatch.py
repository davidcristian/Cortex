"""Dispatch one tool call and audit it. It is the only path a tool runs through (ADR-0009/0013)."""

from collections.abc import Collection, Sequence
from dataclasses import replace

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
from cortex_core.tools import (
    UNSTAMPED,
    ConfirmationRequest,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.untrusted import DENIED_MSG, USER_DECLINED_MSG

# Why confirmation is required, shown verbatim to the user by the overlay (ADR-0022).
_GATE_REASON = "this action is outbound or irreversible and runs only with your approval"

# The result content fed back when the caller's dispatch budget is spent (ADR-0009 budget
# addendum). Phrased so the model stops calling tools and answers with what it already has,
# rather than retrying the same call into a bound that cannot move within the loop.
BUDGET_EXHAUSTED_MSG = (
    "REFUSED: this turn has reached its limit on tool calls, so the tool was not run. Do not "
    "retry this or any other tool call. Answer the user with the information you already have, "
    "and say that you stopped short if the answer is incomplete."
)


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
        gated_names: Collection[str] = (),
    ) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock
        self._confirmer = confirmer
        self._gated_names = frozenset(gated_names)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    async def dispatch(
        self,
        call: ToolCall,
        *,
        stamp: TurnStamp = UNSTAMPED,
        gated: bool = False,
        over_budget: bool = False,
    ) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes."""
        # Overwrite the call's stamp with the turn's (ADR-0018/0027): provenance for built-ins
        # that spawn further work, never authority. The gate below keeps using the explicit
        # ``stamp`` argument, so a model-forged stamp is discarded and feeds nothing.
        call = replace(call, stamp=stamp)
        if over_budget:
            refused = ToolResult(
                call_id=call.id,
                content=BUDGET_EXHAUSTED_MSG,
                is_error=True,
                trust=Trust.TRUSTED,
            )
            return await self._audited(call, refused)
        # The advertised flag OR the authoritative gated set (ADR-0022): a gated tool a flaky
        # sidecar hid from this turn's advertisement snapshot is still gated here.
        gated = gated or call.name in self._gated_names
        if gated:
            if stamp.tainted:
                blocked = ToolResult(
                    call_id=call.id, content=DENIED_MSG, is_error=True, trust=Trust.TRUSTED
                )
                return await self._audited(call, blocked)
            if not await self._confirmed(call):
                declined = ToolResult(
                    call_id=call.id, content=USER_DECLINED_MSG, is_error=True, trust=Trust.TRUSTED
                )
                return await self._audited(call, declined)
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
