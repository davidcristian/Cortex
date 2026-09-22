"""Running one planned round of tool dispatches, and the context each round is given."""

from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass, field

from cortex_core.cadence import CadenceWatch
from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.handoff import EscalationSlot
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.loop_events import StepOutcome, ToolStep, step_summary
from cortex_core.ports import Clock
from cortex_core.progress import ProgressSink, hold_wait
from cortex_core.provenance import SourceKind, as_source
from cortex_core.stops import StopLedger
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_round import RoundPlan, result_message
from cortex_core.tools import ToolCall, ToolSpec, TurnStamp
from cortex_core.untrusted import TaintLedger
from cortex_core.waits import GENERATING, TOOL_RUNNING, Wait


@dataclass(frozen=True, slots=True)
class ToolLoopContext:
    """The collaborators of one tool loop, bundled to stay under the argument limit."""

    dispatcher: ToolDispatcher | None
    clock: Clock
    turn_id: str
    taint: TaintLedger
    nonce: str
    session_id: str
    task_id: str = ""
    item_id: str = ""
    schema: JsonSchema | None = None
    bounds: GenerationBounds | None = None
    budget: DispatchBudget = field(default_factory=DispatchBudget)
    progress: ProgressSink | None = None
    escalation: EscalationSlot | None = None
    cadence: CadenceWatch | None = None
    stops: StopLedger | None = None
    generating: Wait = GENERATING

    @property
    def unit_id(self) -> str:
        """The id this loop's own messages are grouped under: its task, else the turn it serves."""
        return self.task_id or self.turn_id


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
    """What the dispatching turn gives one call, built fresh for each dispatch."""
    return TurnStamp(
        session_id=context.session_id,
        turn_id=context.turn_id,
        task_id=context.task_id,
        item_id=context.item_id,
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
    this_round: list[ToolCall] = []
    dispatched.append(this_round)
    for call, oversized in plan.answered():
        spec = spec_by_name.get(call.name)
        refusal = _refused_by(call, dispatcher, dispatched, context.budget, oversized=oversized)
        if refusal is None:
            this_round.append(call)
        # Only an advertised spec is shown, so no model-written tool name reaches the overlay.
        if refusal is None and spec is not None:
            yield ToolStep(tool_name=spec.name, summary=step_summary(spec))
        # A refused call is dispatched too, because the dispatcher writes the refusal as the
        # call's result: a tool call with no result would make the next request malformed.
        running = context.progress if refusal is None else None
        async with hold_wait(running, TOOL_RUNNING):
            result = await dispatcher.dispatch(
                call,
                stamp=_stamp(context),
                gated=spec is not None and spec.gated,
                refusal=refusal,
            )
        if refusal is None and spec is not None:
            yield StepOutcome(tool_name=spec.name, ok=not result.is_error)
        context.taint.observe(
            result, source=as_source(SourceKind.TOOL, None if spec is None else spec.name)
        )
        working.append(
            result_message(result, context.clock.now(), context.unit_id, nonce=context.nonce)
        )
