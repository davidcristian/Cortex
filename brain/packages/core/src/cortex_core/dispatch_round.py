"""Running one planned round of tool dispatches, and the context every round is configured by."""

from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass, field

from cortex_core.cadence import CadenceWatch
from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.handoff import EscalationSlot
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.loop_events import StepOutcome, ToolStep, step_summary
from cortex_core.ports import Clock
from cortex_core.progress import ProgressSink
from cortex_core.provenance import SourceKind, as_source
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_round import RoundPlan, result_message
from cortex_core.tools import ToolCall, ToolSpec, TurnStamp
from cortex_core.untrusted import TaintLedger


@dataclass(frozen=True, slots=True)
class ToolLoopContext:
    """The per-invocation collaborators of one tool loop (ADR-0013), bundled to stay under the
    argument ceiling.
    """

    dispatcher: ToolDispatcher | None
    clock: Clock
    turn_id: str
    taint: TaintLedger
    nonce: str
    session_id: str
    schema: JsonSchema | None = None
    bounds: GenerationBounds | None = None
    budget: DispatchBudget = field(default_factory=DispatchBudget)
    progress: ProgressSink | None = None
    escalation: EscalationSlot | None = None
    cadence: CadenceWatch | None = None


def _refused_by(
    call: ToolCall,
    dispatcher: ToolDispatcher,
    dispatched: Sequence[Sequence[ToolCall]],
    budget: DispatchBudget,
    *,
    oversized: bool,
) -> DispatchRefusal | None:
    """Which bound refuses this call before it can run, or ``None`` when it may go ahead."""
    if oversized:
        return DispatchRefusal.ROUND_OVERSIZED
    if not dispatcher.admits(call, dispatched):
        return DispatchRefusal.REDUNDANT
    if not budget.charge(dispatcher.cost_of(call.name)):
        return DispatchRefusal.BUDGET
    return None


def _stamp(context: ToolLoopContext) -> TurnStamp:
    """What the dispatching turn hands one call, built fresh per dispatch (ADR-0027)."""
    return TurnStamp(
        session_id=context.session_id,
        tainted=context.taint.tainted,
        sources=context.taint.sources,
        budget=context.budget,
        progress=context.progress,
        escalation=context.escalation,
    )


async def run_round(
    plan: RoundPlan,
    dispatcher: ToolDispatcher,
    spec_by_name: Mapping[str, ToolSpec],
    dispatched: list[list[ToolCall]],
    context: ToolLoopContext,
    working: list[Message],
) -> AsyncGenerator[ToolStep | StepOutcome, None]:
    """Dispatch every call one planned round answers, appending each result to ``working``."""
    # This round's dispatched calls, appended to the loop's history before the round runs so
    # the policy sees the round in progress as its last group (ADR-0009 salience addendum).
    this_round: list[ToolCall] = []
    dispatched.append(this_round)
    for call, oversized in plan.answered():
        spec = spec_by_name.get(call.name)
        refusal = _refused_by(call, dispatcher, dispatched, context.budget, oversized=oversized)
        if refusal is None:
            # Recorded when the call is handed over, not when it answers: a gate denial and
            # a declined confirmation are `is_error` results too, so counting only successes
            # would leave a declined gated call free to re-prompt the user every round.
            this_round.append(call)
        if refusal is None and spec is not None:
            yield ToolStep(tool_name=spec.name, summary=step_summary(spec))
        result = await dispatcher.dispatch(
            call,
            stamp=_stamp(context),
            gated=spec is not None and spec.gated,
            refusal=refusal,
        )
        if refusal is None and spec is not None:
            yield StepOutcome(tool_name=spec.name, ok=not result.is_error)
        # An untrusted result's source is the tool it came through, named by the registry's
        # own advertisement. A call that matched no spec attributes nothing rather than
        # falling back to the model's chosen name.
        context.taint.observe(
            result, source=as_source(SourceKind.TOOL, None if spec is None else spec.name)
        )
        working.append(
            result_message(result, context.clock.now(), context.turn_id, nonce=context.nonce)
        )
