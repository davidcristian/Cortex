"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013).

Both the cortex ``TurnEngine`` and a ``SubagentRunner`` do the same thing: stream from a model
with tools available; when the model emits tool calls, dispatch each through the audited
``ToolDispatcher`` and feed the results back; repeat until a final text answer, ``MAX_TOOL_STEPS``
rounds, or a spent ``DispatchBudget`` (the four bounds are independent: rounds cap how long the
loop runs, the budget caps how much of the outside world it may touch, ADR-0009 budget addendum,
the ``SaliencePolicy`` refuses a call this loop has already made, salience addendum, and
``plan_round`` caps how wide one round may be, round-cap addendum; the
budget is a pool the whole turn shares, so a spawned subagent draws from the same allowance
rather than starting a fresh one, while salience and the round cap are per loop and per round,
since a repeat is redundant only against the context that holds its answer and a round is only
as wide as the model made it). That loop (inlined in ``handle_turn`` before Slice 7)
lives here so both
callers reuse it verbatim: one loop, one bound, one audited dispatch path. The loop mutates the
``working`` message list in place (appending the tool-call and result messages) and yields each
assistant reply delta (a ``str``), any ``ReasoningDelta`` a reasoning model streams (ADR-0020),
and a ``ToolStep`` per audited dispatch (ADR-0009 addendum); the caller accumulates the reply
text and decides what to do with each (the cortex surfaces reasoning as status and tool steps
as activity, a subagent drops both).

The loop is also where the untrusted-content boundary is drawn (ADR-0013): an UNTRUSTED result
is fenced by ``wrap_untrusted`` before it re-enters the context, the per-turn ``TaintLedger``
observes every result, marking taint so a later gated call is confirmed, collecting the
URLs untrusted content carried so the output guardrail can redact a laundered one (ADR-0015),
and noting the advertised tool it came through as that content's provenance (ADR-0027
addendum), which the next dispatch's stamp carries; the ledger + nonce ride in the
``ToolLoopContext`` bundle (keeping the loop within its argument ceiling). Both callers
construct the ledger, so both accumulate taint by the same mechanism.
"""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass, field

from cortex_core.conversation import Message
from cortex_core.dispatch import DispatchRefusal, ToolDispatcher
from cortex_core.inference import JsonSchema, ReasoningChunk
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.provenance import SourceKind, as_source
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_round import call_message, plan_round, result_message
from cortex_core.tools import ToolCall, ToolSpec, TurnStamp
from cortex_core.untrusted import TaintLedger

# Upper bound on inference↔tool rounds in one loop (ADR-0009): a safety net against a model
# that never stops calling tools. On exhaustion the loop ends with the text produced so far.
MAX_TOOL_STEPS = 8

# Upper bound on a ToolStep summary: the chip is one slim line, and an advertised description
# is sidecar-authored text of arbitrary length (ADR-0009 addendum).
MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A delta of the model's reasoning trace, surfaced by the loop distinctly from reply text
    (ADR-0020). The loop's yield vocabulary is ``str`` (reply text), ``ReasoningDelta``, or
    ``ToolStep``: reply text accumulates into the answer and is persisted, a reasoning delta is
    ephemeral status and is never added to the assistant message nor fed back into the context.
    """

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded by the loop immediately before the
    dispatch so a consumer can surface it while the tool works (ADR-0009 addendum). Ephemeral
    like ``ReasoningDelta``: the cortex engine maps it to the domain ``ToolActivity`` event,
    a subagent drops it. Both fields are copied straight off the advertised ``ToolSpec``
    (``tool_name`` is ``spec.name``, ``summary`` is ``_step_summary``): nothing the model
    authored, neither the call name nor its arguments, ever rides this event.
    """

    tool_name: str
    summary: str


def _step_summary(spec: ToolSpec) -> str:
    """The chip text for one dispatch: the advertised description's first line, capped, with
    the advertised name as the fallback when the description is empty.

    Registry-authored by construction, because a ``ToolStep`` is only yielded for a call that
    matched an advertised spec (``stream_tool_loop``). The model's call name and arguments
    never reach it: a value the model authored would be a display channel the reply-side
    guardrail (ADR-0015) never inspects, exactly the laundering surface this event must not open.
    """
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]


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
    total the way a per-invocation count did (ADR-0009 turn-wide addendum).
    """

    dispatcher: ToolDispatcher | None
    clock: Clock
    turn_id: str
    taint: TaintLedger
    nonce: str
    session_id: str
    schema: JsonSchema | None = None
    budget: DispatchBudget = field(default_factory=DispatchBudget)


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


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding reply-text deltas (``str``),
    reasoning deltas (``ReasoningDelta``, ADR-0020), and a ``ToolStep`` per audited dispatch
    (ADR-0009 addendum).

    The loop advertises exactly the tools it can dispatch: the dispatcher's tools when present,
    none otherwise. With ``dispatcher`` None (or once the model stops calling tools) the loop
    ends after one inference step. Four bounds apply: ``MAX_TOOL_STEPS`` rounds,
    ``context.budget`` summed across them (ADR-0009 budget addendum), each call charged the
    dispatcher's price for it (ADR-0009 cost addendum), the dispatcher's salience policy,
    which refuses a call this loop has already made (salience addendum) before it is charged,
    and ``plan_round``, which drops the calls one round emits past ``MAX_CALLS_PER_ROUND`` and
    refuses the one slot it keeps past the cap so the model reads what happened (round-cap
    addendum). Once a call does not fit, the budget
    closes: that call and every later one is refused by the dispatcher and audited, and the
    rounds that remain are how the model learns of it and still answers. The budget may be a
    pool shared with the loops of spawned subagents, in which case all of that is turn-wide.
    Each tool call is dispatched through the audited dispatcher, with
    gated calls confirmed against the turn's taint (ADR-0013). Its result marks the taint ledger
    and is fed back (fenced when untrusted) as a ``Role.TOOL`` message before re-inference.
    Reasoning deltas and tool steps are surfaced live but never join ``step_text``, so they are
    neither persisted with the assistant message nor fed back into the next step's context.
    """
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    gated_by_name = {spec.name: spec.gated for spec in specs}
    spec_by_name = {spec.name: spec for spec in specs}
    # The pool this loop spends from, summed across its rounds and shared with any subagent it
    # spawns (ADR-0009 budget addendum + turn-wide addendum). A call is charged its policy cost
    # rather than a flat one (ADR-0009 cost addendum), so a tool a user declared expensive
    # exhausts the turn faster than a cheap one.
    budget = context.budget
    # Every call this loop has dispatched, grouped by the round that emitted it, which is what
    # the salience policy reads (ADR-0009 salience addendum). A local rather than shared state on
    # the budget or the dispatcher, and deliberately not turn-wide the way the pool is: a repeat
    # is redundant only against the `working` messages that already hold its answer, and a
    # subagent's own loop can see neither this list nor a sibling's results.
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
        # How wide this round is allowed to be (ADR-0009 round-cap addendum). Everything past
        # the cap is dropped here, the assistant message's own tool_calls included, so it
        # appends nothing at all; a per-call refusal would have grown the context exactly as
        # much as the calls it refused.
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
            # Refused by any bound, the call is still handed to the dispatcher, which refuses
            # it and audits the refusal (ADR-0009 budget addendum). Breaking out instead would
            # strand this round's tool_calls without their Role.TOOL answers, so the next round's
            # re-inference would send a malformed conversation, and would refuse dispatches
            # that no audit record ever sees.
            refusal = _refused_by(call, dispatcher, dispatched, budget, oversized=oversized)
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
                yield ToolStep(tool_name=spec.name, summary=_step_summary(spec))
            # The advertised gated flag is a hint; the dispatcher OR-s it with its own
            # authoritative gated-name set, so a tool a flaky sidecar hid from this snapshot
            # (skip mode) and later recovered is still gated at dispatch (ADR-0022). The
            # stamp is built fresh per dispatch (ADR-0027): the taint bit is live and can
            # flip mid-loop as untrusted results arrive.
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
