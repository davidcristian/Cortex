"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013)."""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass, field

from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.handoff import EscalationSlot
from cortex_core.inference import JsonSchema, ReasoningChunk
from cortex_core.loop_events import ReasoningDelta, ToolStep, step_summary
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.progress import ProgressSink
from cortex_core.provenance import SourceKind, as_source
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_round import call_message, plan_round, result_message
from cortex_core.tools import ToolCall, TurnStamp
from cortex_core.untrusted import TaintLedger

# Upper bound on inference↔tool rounds in one loop (ADR-0009): a safety net against a model
# that never stops calling tools. On exhaustion the loop ends with the text produced so far.
MAX_TOOL_STEPS = 8


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
    budget: DispatchBudget = field(default_factory=DispatchBudget)
    progress: ProgressSink | None = None
    escalation: EscalationSlot | None = None


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


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding reply-text deltas (``str``),
    reasoning deltas (``ReasoningDelta``, ADR-0020), and a ``ToolStep`` per audited dispatch
    (ADR-0009 addendum).
    """
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    gated_by_name = {spec.name: spec.gated for spec in specs}
    spec_by_name = {spec.name: spec for spec in specs}
    budget = context.budget
    dispatched: list[list[ToolCall]] = []
    for _step in range(MAX_TOOL_STEPS):
        calls: list[ToolCall] = []
        step_text: list[str] = []
        deltas = backend.stream(model, working, tools=specs, schema=context.schema)
        try:
            async for event in deltas:
                if isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, ReasoningChunk):
                    yield ReasoningDelta(event.text)
                else:
                    step_text.append(event.text)
                    yield event.text
        finally:
            # Runs on normal exhaustion, backend failure, and consumer aclose() alike: an
            # abandoned backend generator must not linger half-suspended.
            if isinstance(deltas, AsyncGenerator):
                await deltas.aclose()
        if not calls or dispatcher is None:
            break
        plan = plan_round(calls)
        working.append(
            call_message("".join(step_text), plan.calls, context.clock.now(), context.turn_id)
        )
        # This round's dispatched calls, appended to the loop's history before the round runs so
        # the policy sees the round in progress as its last group (ADR-0009 salience addendum).
        this_round: list[ToolCall] = []
        dispatched.append(this_round)
        for call, oversized in plan.answered():
            # The advertised spec this call matched, or None for a name no snapshot carried. It
            # is both the chip's text and the call's provenance below, and using it rather than
            # `call.name` is what keeps either from carrying a string the model authored.
            spec = spec_by_name.get(call.name)
            refusal = _refused_by(call, dispatcher, dispatched, budget, oversized=oversized)
            if refusal is None:
                # Recorded when the call is handed over, not when it answers: a gate denial and
                # a declined confirmation are `is_error` results too, so counting only successes
                # would leave a declined gated call free to re-prompt the user every round.
                this_round.append(call)
            if refusal is None and spec is not None:
                yield ToolStep(tool_name=spec.name, summary=step_summary(spec))
            result = await dispatcher.dispatch(
                call,
                stamp=TurnStamp(
                    session_id=context.session_id,
                    tainted=context.taint.tainted,
                    # Where the taint bit came from, as live as the bit itself (ADR-0027
                    # addendum): what the turn had read *before* this call, which is exactly
                    # what a consumer deciding about this call may reason over.
                    sources=context.taint.sources,
                    # The pool travels to whatever this call spawns, so a subagent draws from
                    # the turn's remaining allowance instead of starting a fresh one.
                    budget=budget,
                    # And the stream's progress channel travels with it, so a built-in that
                    # spawns subagents surfaces their steps onto this turn's overlay while the
                    # loop is suspended inside the dispatch below (ADR-0010 progress addendum).
                    progress=context.progress,
                    # And the turn's handoff slot (ADR-0030): the escalate built-in writes its
                    # brief here, per call off the stamp, so one shared tool instance never
                    # holds a turn's slot as state.
                    escalation=context.escalation,
                ),
                gated=gated_by_name.get(call.name, False),
                refusal=refusal,
            )
            # An untrusted result's source is the tool it came through, named by the registry's
            # own advertisement. A call that matched no spec attributes nothing rather than
            # falling back to the model's chosen name.
            context.taint.observe(
                result, source=as_source(SourceKind.TOOL, None if spec is None else spec.name)
            )
            working.append(
                result_message(result, context.clock.now(), context.turn_id, nonce=context.nonce)
            )
