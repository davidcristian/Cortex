"""Dispatch one tool call and audit it."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType

from cortex_core.errors import ToolError
from cortex_core.ports import Clock, Confirmer, ToolAuditSink, ToolRegistry
from cortex_core.progress import hold_wait
from cortex_core.tool_budget import UNIFORM_COST, ToolCostPolicy
from cortex_core.tool_round import MAX_CALLS_PER_ROUND
from cortex_core.tool_salience import REPEAT_SALIENCE, SaliencePolicy
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
from cortex_core.waits import USER_ASKED

_GATE_REASON = "this action is outbound or irreversible and runs only with your approval"

BUDGET_EXHAUSTED_MSG = (
    "REFUSED: this turn has reached its limit on tool calls, so the tool was not run. Do not "
    "retry this or any other tool call. Answer the user with the information you already have, "
    "and say that you stopped short if the answer is incomplete."
)

REDUNDANT_MSG = (
    "REFUSED: this exact tool call has already run in this turn, so it was not run again. Its "
    "result is already in this conversation above. Use that result, or call a different tool, "
    "but do not repeat this call."
)

ROUND_OVERSIZED_MSG = (
    f"REFUSED: one reply may ask for at most {MAX_CALLS_PER_ROUND} tool calls at once. This "
    "reply asked for more, so this call and every call after it were dropped without running. "
    "The calls before it did run, and their results are in this conversation above. Ask for "
    "whatever you still need in your next reply, a few calls at a time."
)


class DispatchRefusal(Enum):
    """Why the caller refused a call before it could run, and what the model is told."""

    BUDGET = BUDGET_EXHAUSTED_MSG
    REDUNDANT = REDUNDANT_MSG
    ROUND_OVERSIZED = ROUND_OVERSIZED_MSG

    @property
    def message(self) -> str:
        """The refusal text fed back to the model as the call's result."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DispatchPolicy:
    """What the composition root declares about dispatching, in one value."""

    gated_names: Collection[str] = ()
    costs: ToolCostPolicy = UNIFORM_COST
    salience: SaliencePolicy = REPEAT_SALIENCE
    gate_reasons: Mapping[str, str] = field(default_factory=dict[str, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "gated_names", frozenset(self.gated_names))
        object.__setattr__(self, "gate_reasons", MappingProxyType(dict(self.gate_reasons)))


DEFAULT_DISPATCH_POLICY = DispatchPolicy()


class ToolDispatcher:
    """Run a tool call through the registry, ask for confirmation when needed, and audit it."""

    def __init__(
        self,
        registry: ToolRegistry,
        audit: ToolAuditSink,
        clock: Clock,
        *,
        confirmer: Confirmer | None = None,
        policy: DispatchPolicy = DEFAULT_DISPATCH_POLICY,
    ) -> None:
        self._registry = registry
        self._audit = audit
        self._clock = clock
        self._confirmer = confirmer
        self._policy = policy

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The tools available to advertise to the model (delegates to the registry)."""
        return await self._registry.describe_tools()

    def cost_of(self, name: str) -> int:
        """What dispatching ``name`` costs against the caller's budget."""
        return self._policy.costs.cost_of(name)

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Whether ``call`` is worth dispatching, given what the caller has already run."""
        return self._policy.salience.admits(call, dispatched)

    async def dispatch(
        self,
        call: ToolCall,
        *,
        stamp: TurnStamp = UNSTAMPED,
        gated: bool = False,
        refusal: DispatchRefusal | None = None,
    ) -> ToolResult:
        """Invoke ``call``, audit the outcome, and return the result the model consumes."""
        # The caller's stamp replaces whatever the call arrived with, so a model-written stamp
        # is discarded. The taint check below reads the ``stamp`` argument for the same reason.
        call = replace(call, stamp=stamp)
        if refusal is not None:
            refused = ToolResult(
                call_id=call.id,
                content=refusal.message,
                is_error=True,
                trust=Trust.TRUSTED,
            )
            return await self._audited(call, refused)
        # A tool a failing sidecar left out of this turn's list still needs confirmation.
        gated = gated or call.name in self._policy.gated_names
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
            result = ToolResult(
                call_id=call.id, content=str(err), is_error=True, trust=Trust.TRUSTED
            )
        return await self._audited(call, result)

    async def _confirmed(self, call: ToolCall) -> bool:
        """Ask the confirmer to approve the call; with no confirmer the call is refused."""
        if self._confirmer is None:
            return False
        request = ConfirmationRequest(
            tool_name=call.name,
            arguments=call.arguments,
            reason=self._policy.gate_reasons.get(call.name, _GATE_REASON),
        )
        async with hold_wait(call.stamp.progress, USER_ASKED):
            return await self._confirmer.confirm(request)

    async def _audited(self, call: ToolCall, result: ToolResult) -> ToolResult:
        """Record one audit line (its provenance, the work it was for, the call) and return it."""
        await self._audit.record(
            ToolInvocation(
                name=call.name,
                arguments=call.arguments,
                ok=not result.is_error,
                detail=result.content,
                at=self._clock.now(),
                trust=result.trust,
                call_id=call.id,
                session_id=call.stamp.session_id,
                turn_id=call.stamp.turn_id,
                task_id=call.stamp.task_id,
                item_id=call.stamp.item_id,
            )
        )
        return result
