"""Running one planned round of tool dispatches, and the context every round is configured by.

Split from ``tool_loop.py`` when the post-dispatch outcome landed (ADR-0029 outcome addendum)
and the loop reached both the complexity ceiling and the 300-line cap. The seam between the two
modules is the loop's own sentence: ``tool_loop.py`` infers, then runs the round this module
owns. ``tool_round.py`` is the third piece and stays pure arithmetic (how wide a round may be);
nothing here decides that.

``ToolLoopContext`` lives here rather than beside the loop because the round is what reads
almost all of it: the loop itself touches only ``dispatcher``, ``budget`` and ``schema``, while
the clock, turn id, ledger, nonce, session, progress sink and escalation slot are all things a
dispatch carries. ``tool_loop`` re-exports it, so every existing
``from cortex_core.tool_loop import ToolLoopContext`` keeps resolving.

Pure: the only I/O is through the ports the caller hands in on the context.
"""

from collections.abc import AsyncGenerator, Mapping, Sequence
from dataclasses import dataclass, field

from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.handoff import EscalationSlot
from cortex_core.inference import JsonSchema
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
    argument ceiling. ``dispatcher`` is the audited tool gateway (``None`` = a no-tools turn);
    ``taint`` is the turn-local ledger the loop marks on each untrusted result; ``nonce`` fences
    those results; ``session_id`` is the originating chat the loop stamps onto each dispatch
    (ADR-0027; ``""`` for a session-less caller, e.g. a subagent); ``schema`` (ADR-0028), when
    set, constrains the model's output to that JSON Schema (a constrained tool-less subagent
    envelope; ``None`` for the cortex and every tool-enabled path); ``budget`` (ADR-0009 budget
    addendum) caps what may be spent on dispatches across the loop's rounds. What each call
    spends comes from the dispatcher's ``ToolCostPolicy`` (ADR-0009 cost addendum), so the price
    of a tool travels with the gateway that runs it rather than being restated here.

    The budget is the one collaborator a caller may **share**: a context built without one gets
    its own pool at ``MAX_TOOL_DISPATCHES``, while a subagent spawned from a cortex turn is
    handed that turn's pool (via the dispatch ``TurnStamp``), so delegation cannot multiply the
    total the way a per-invocation count did (ADR-0009 turn-wide addendum). ``progress`` (ADR-0010
    progress addendum) is the stream's side channel the loop stamps onto each dispatch, so a
    built-in that spawns further work (``spawn_subagents``) can surface a subagent's steps onto
    the overlay while the loop's own generator is suspended inside that dispatch; ``None`` (a
    subagent's own inner loop, a session-less caller) leaves such work unsurfaced, keeping
    delegation depth-1 in what reaches the overlay as it is in the tree. ``escalation``
    (ADR-0030) is the turn's handoff slot, threaded exactly like ``progress`` so the
    ``escalate_to_brain`` built-in reads it off each dispatch's stamp; ``None`` (the default,
    every escalation-less caller) leaves the tool refusing honestly.
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
    """Which bound refuses this call before it can run, or ``None`` when it may go ahead.

    The overflow slot of a truncated round is refused first (ADR-0009 round-cap addendum),
    ahead of both the other bounds and for the same reason salience precedes the budget: it
    reaches nothing, so neither the turn's allowance nor this loop's repeat count should record
    it. It is a fact about the round's shape, settled before anything about the call itself.

    Salience is asked next, and a call it refuses is never charged: the budget bounds reach
    into the outside world and a repeat reaches nothing, so charging it would spend the turn's
    allowance on the model's own repetition (ADR-0009 salience addendum). The order's one cost is
    that a repeat emitted past a closed budget reports redundancy rather than exhaustion, the
    less useful of two true statements.

    ``charge`` spends when the call fits and closes the pool for good when it does not, so a
    cheaper call behind an unaffordable one does not trickle through (ADR-0009 cost addendum).
    Closing is turn-wide once a subagent shares the pool: a runaway delegate stops its siblings
    and the rest of this loop too, which is what keeps ``BUDGET_EXHAUSTED_MSG``'s "this turn has
    reached its limit" true. Both calls have side effects, so the order is behavior, not style.
    """
    if oversized:
        return DispatchRefusal.ROUND_OVERSIZED
    if not dispatcher.admits(call, dispatched):
        return DispatchRefusal.REDUNDANT
    if not budget.charge(dispatcher.cost_of(call.name)):
        return DispatchRefusal.BUDGET
    return None


def _stamp(context: ToolLoopContext) -> TurnStamp:
    """What the dispatching turn hands one call, built fresh per dispatch (ADR-0027).

    Fresh rather than hoisted because the taint bit is live and can flip mid-round as untrusted
    results arrive, and the sources behind it grow with it. The budget, the progress channel and
    the escalation slot are live shared handles that travel to whatever the call spawns: a
    subagent draws from the turn's remaining allowance instead of a fresh one, surfaces its own
    steps onto this turn's overlay while the loop is suspended inside the dispatch, and the
    escalate built-in writes its brief into the turn's own slot rather than into tool state.
    """
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
    """Dispatch every call one planned round answers, appending each result to ``working``.

    Yields a ``ToolStep`` before each announced dispatch and the ``StepOutcome`` that settles it
    after, **paired**: both are guarded by the identical condition, so nothing a consumer lit on
    a step is left unsettled. The one way out without an outcome is this generator being closed
    mid-dispatch, which ends the turn and takes the surface with it.

    ``dispatcher`` is a plain ``ToolDispatcher`` rather than the context's optional one, because
    a round only exists when the loop found tools to dispatch. ``dispatched`` is the loop's own
    per-round history, appended to before this round runs so the salience policy sees the round
    in progress as its last group (ADR-0009 salience addendum).
    """
    # This round's dispatched calls, appended to the loop's history before the round runs so
    # the policy sees the round in progress as its last group (ADR-0009 salience addendum).
    this_round: list[ToolCall] = []
    dispatched.append(this_round)
    for call, oversized in plan.answered():
        # The advertised spec this call matched, or None for a name no snapshot carried. It
        # is the chip's text, the outcome's name, and the call's provenance below, and using it
        # rather than `call.name` is what keeps any of them from carrying a model-authored
        # string. The advertised gated flag rides it too; the dispatcher OR-s that with its own
        # authoritative gated-name set, so a tool a flaky sidecar hid from this snapshot (skip
        # mode) and later recovered is still gated at dispatch (ADR-0022).
        spec = spec_by_name.get(call.name)
        # Refused by any bound, the call is still handed to the dispatcher, which refuses
        # it and audits the refusal (ADR-0009 budget addendum). Breaking out instead would
        # strand this round's tool_calls without their Role.TOOL answers, so the next round's
        # re-inference would send a malformed conversation, and would refuse dispatches
        # that no audit record ever sees.
        refusal = _refused_by(call, dispatcher, dispatched, context.budget, oversized=oversized)
        if refusal is None:
            # Recorded when the call is handed over, not when it answers: a gate denial and
            # a declined confirmation are `is_error` results too, so counting only successes
            # would leave a declined gated call free to re-prompt the user every round.
            this_round.append(call)
        # Surface activity only for a dispatched call that matched an advertised spec, so
        # the chip's name and summary are both registry-authored (ADR-0009 addendum). A call
        # to an unadvertised name (a model hallucination, or a tool skip-mode hid) still
        # dispatches below and fails as its usual is_error result, but never renders a chip
        # carrying the model's chosen string. A refused call renders no chip either: a chip
        # means a tool is running now.
        if refusal is None and spec is not None:
            yield ToolStep(tool_name=spec.name, summary=step_summary(spec))
        result = await dispatcher.dispatch(
            call,
            stamp=_stamp(context),
            gated=spec is not None and spec.gated,
            refusal=refusal,
        )
        # And how it ended, under the identical condition the chip was yielded under, so every
        # announced dispatch is settled exactly once (ADR-0029 outcome addendum). Deliberately
        # after the dispatch and outside every branch inside it: the taint denial, a declined
        # confirmation, a registry fault, and the tool's own failure all resolve into the one
        # `result` above, so no path out of a dispatch reports nothing. `ok` is the audit line's
        # own verdict off that same result, so a display surface and the audit trail cannot
        # disagree about one dispatch.
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
