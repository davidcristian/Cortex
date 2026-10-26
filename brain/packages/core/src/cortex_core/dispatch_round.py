"""Running one planned round of tool dispatches, and the context each round is given."""

from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass, field

from cortex_core.cadence import CadenceWatch
from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.handoff import EscalationSlot
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.loop_events import StepOutcome, ToolStep, step_summary
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.ports import Clock
from cortex_core.progress import ProgressSink, hold_wait
from cortex_core.provenance import SourceKind, as_source
from cortex_core.stops import StopLedger
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_cut import ResultRoom
from cortex_core.tool_round import RoundPlan, result_message
from cortex_core.tool_salience import asks_the_same
from cortex_core.tool_tail import tail_count
from cortex_core.tools import ToolCall, ToolSpec, Trust, TurnStamp
from cortex_core.untrusted import USER_DECLINED_MSG, TaintLedger
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
    # The calls the person pressed Deny on in this loop, so an identical one is not asked again.
    declined: list[ToolCall] = field(default_factory=list[ToolCall])

    @property
    def unit_id(self) -> str:
        """The id this loop's own messages are grouped under: its task, else the turn it serves."""
        return self.task_id or self.turn_id


@dataclass(frozen=True, slots=True)
class LoopRecord:
    """What one loop has done: the calls it dispatched, by round, and the room its results use."""

    dispatched: list[list[ToolCall]] = field(default_factory=list[list[ToolCall]])
    room: ResultRoom = field(default_factory=ResultRoom)


def _refused_by(
    call: ToolCall,
    dispatcher: ToolDispatcher,
    dispatched: Sequence[Sequence[ToolCall]],
    context: ToolLoopContext,
    *,
    oversized: bool,
) -> DispatchRefusal | None:
    """Which bound refuses this call before it can run, or ``None`` when it may go ahead."""
    if oversized:
        return DispatchRefusal.ROUND_OVERSIZED
    if any(asks_the_same(call, declined) for declined in context.declined):
        return DispatchRefusal.DECLINED
    if not dispatcher.admits(call, dispatched):
        return DispatchRefusal.REDUNDANT
    if not context.budget.charge(dispatcher.cost_of(call.name)):
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
        recalled_only=context.taint.recalled_only,
        forgotten=context.taint.forgotten,
        sources=context.taint.sources,
        budget=context.budget,
        progress=context.progress,
        escalation=context.escalation,
    )


async def run_round(
    plan: RoundPlan,
    dispatcher: ToolDispatcher,
    spec_by_name: Mapping[str, ToolSpec],
    record: LoopRecord,
    context: ToolLoopContext,
    working: list[Message],
) -> AsyncGenerator[ToolStep | StepOutcome, None]:
    """Dispatch every call one planned round answers, appending each result to ``working``."""
    this_round: list[ToolCall] = []
    record.dispatched.append(this_round)
    for index, (call, oversized) in enumerate(plan.answered()):
        spec = spec_by_name.get(call.name)
        refusal = _refused_by(call, dispatcher, record.dispatched, context, oversized=oversized)
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
                confirm_required=spec is not None and spec.confirm_required,
                refusal=refusal,
            )
        if refusal is None and result.content == USER_DECLINED_MSG:
            context.declined.append(call)
        if refusal is None and spec is not None:
            yield StepOutcome(tool_name=spec.name, ok=not result.is_error)
        if spec is not None and spec.name == FORGET_UNTRUSTED_TOOL_NAME and not result.is_error:
            context.taint.forgotten = True
        context.taint.observe(
            result, source=as_source(SourceKind.TOOL, None if spec is None else spec.name)
        )
        # A refusal or failure the brain wrote is never cut, so the model still reads why.
        if result.is_error and result.trust is Trust.TRUSTED:
            cut = record.room.whole(result.content)
        else:
            # The calls of a round not yet answered share what is left, so the first is not all.
            cut = record.room.cut(
                result.content, share=len(plan.calls) - index, keep_end=tail_count(call) is not None
            )
        working.append(
            result_message(
                result, context.clock.now(), context.unit_id, nonce=context.nonce, cut=cut
            )
        )
