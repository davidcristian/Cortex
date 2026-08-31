"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013).

Both the cortex ``TurnEngine`` and a ``SubagentRunner`` do the same thing: stream from a model
with tools available; when the model emits tool calls, dispatch each through the audited
``ToolDispatcher`` and feed the results back; repeat until a final text answer, ``MAX_TOOL_STEPS``
rounds, or a spent ``DispatchBudget`` (the five bounds are independent: rounds cap how long the
loop runs, the budget caps how much of the outside world it may touch, ADR-0009 budget addendum,
the ``SaliencePolicy`` refuses a call this loop has already made, salience addendum,
``plan_round`` caps how wide one round may be, round-cap addendum, and ``context.bounds`` caps how
far any one completion decodes, ADR-0005 total-cap addendum; the
budget is a pool the whole turn shares, so a spawned subagent draws from the same allowance
rather than starting a fresh one, while salience and the round cap are per loop and per round,
since a repeat is redundant only against the context that holds its answer and a round is only
as wide as the model made it). That loop, once inlined in ``handle_turn``, lives here so both
callers reuse it verbatim under one bound and one audited dispatch path. The loop mutates the
``working`` message list in place (appending the tool-call and result messages) and yields each
assistant reply delta (a ``str``), any ``ReasoningDelta`` a reasoning model streams (ADR-0020),
a ``ToolStep`` per audited dispatch (ADR-0009 addendum), and the ``StepOutcome`` settling it
(ADR-0029 outcome addendum); the caller accumulates the reply text and decides what to do with
each (the cortex surfaces reasoning as status, tool steps as activity and outcomes as the
capture indicator's evidence, a subagent drops all but its steps).

The module owns the loop and nothing else. Running one round of dispatches (and the
``ToolLoopContext`` almost every field of which a round reads) lives in ``dispatch_round.py``,
split off when the outcome landed and this file reached both the complexity ceiling and the
300-line cap; the context is re-exported here so every existing import keeps resolving. How wide
a round may be is ``tool_round.py``'s pure arithmetic. The seam between the three follows the
loop's own steps: infer, plan the round, run it.

The loop is also where the untrusted-content boundary is drawn (ADR-0013): an UNTRUSTED result
is fenced by ``wrap_untrusted`` before it re-enters the context, the per-turn ``TaintLedger``
observes every result, marking taint so a later gated call is confirmed, collecting the
URLs untrusted content carried so the output guardrail can redact a laundered one (ADR-0015),
and noting the advertised tool it came through as that content's provenance (ADR-0027
addendum), which the next dispatch's stamp carries; the ledger + nonce ride in the
``ToolLoopContext`` bundle (keeping the loop within its argument ceiling). Both callers
construct the ledger, so both accumulate taint by the same mechanism.
"""

from collections.abc import AsyncGenerator

from cortex_core.conversation import Message
from cortex_core.dispatch_round import ToolLoopContext, run_round
from cortex_core.inference import DecodeCadence, DecodeStop, ReasoningChunk, TextChunk
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.ports import InferenceBackend
from cortex_core.tool_round import call_message, plan_round
from cortex_core.tools import ToolCall

# Re-exported so every existing `from cortex_core.tool_loop import ToolLoopContext` keeps
# resolving after the round split; the context itself now lives beside the round that reads it.
__all__ = ["MAX_TOOL_STEPS", "ToolLoopContext", "stream_tool_loop"]

# Upper bound on inference↔tool rounds in one loop (ADR-0009): a safety net against a model
# that never stops calling tools. On exhaustion the loop ends with the text produced so far.
MAX_TOOL_STEPS = 8


def _reply_text(
    event: TextChunk | DecodeCadence | DecodeStop, context: ToolLoopContext
) -> str | None:
    """The reply text an event carries, or ``None`` once it has been absorbed as a machine fact.

    The two closing events describe the machine rather than the turn: how fast it decoded
    (ADR-0030 spill-watch addendum) and why it stopped (ADR-0005 finish-reason addendum). Neither
    is something the turn said, so neither is ever yielded into a stream a user reads; each goes to
    the collaborator on the context that asked for it, and a caller that handed none drops it,
    which costs nothing because nothing else in the loop reads either.
    """
    if isinstance(event, DecodeCadence):
        if context.cadence is not None:
            context.cadence.observe(event)
        return None
    if isinstance(event, DecodeStop):
        if context.stops is not None:
            context.stops.observe(event)
        return None
    return event.text


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding reply-text deltas (``str``),
    reasoning deltas (``ReasoningDelta``, ADR-0020), a ``ToolStep`` per audited dispatch
    (ADR-0009 addendum), and the ``StepOutcome`` that settles it (ADR-0029 outcome addendum).

    The loop advertises exactly the tools it can dispatch: the dispatcher's tools when present,
    none otherwise. With ``dispatcher`` None (or once the model stops calling tools) the loop
    ends after one inference step. Five bounds apply: ``MAX_TOOL_STEPS`` rounds,
    ``context.budget`` summed across them (ADR-0009 budget addendum), each call charged the
    dispatcher's price for it (ADR-0009 cost addendum), the dispatcher's salience policy,
    which refuses a call this loop has already made (salience addendum) before it is charged,
    ``plan_round``, which drops the calls one round emits past ``MAX_CALLS_PER_ROUND`` and
    refuses the one slot it keeps past the cap so the model reads what happened (round-cap
    addendum), and ``context.bounds``, which rides every completion this loop asks for so no
    single one decodes without end (ADR-0005 total-cap addendum); rounds and that cap multiply,
    so what they bound together is the decoding of a whole loop rather than of one completion.
    Once a call does not fit, the budget
    closes: that call and every later one is refused by the dispatcher and audited, and the
    rounds that remain are how the model learns of it and still answers. The budget may be a
    pool shared with the loops of spawned subagents, in which case all of that is turn-wide.
    Each tool call is dispatched through the audited dispatcher, with
    gated calls confirmed against the turn's taint (ADR-0013). Its result marks the taint ledger
    and is fed back (fenced when untrusted) as a ``Role.TOOL`` message before re-inference.
    Reasoning deltas, tool steps, and step outcomes are surfaced live but never join
    ``step_text``, so they are neither persisted with the assistant message nor fed back into
    the next step's context.

    Steps and outcomes are paired by the round that emits them: exactly one ``StepOutcome``
    follows each ``ToolStep``, so an indicator a consumer turned on for a step always gets its
    settling event. The one exception is this generator being closed mid-dispatch, which ends
    the turn and the surface with it.
    """
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    spec_by_name = {spec.name: spec for spec in specs}
    # Every call this loop has dispatched, grouped by the round that emitted it, which is what
    # the salience policy reads (ADR-0009 salience addendum). A local rather than shared state on
    # the budget or the dispatcher, and deliberately not turn-wide the way the pool is: a repeat
    # is redundant only against the `working` messages that already hold its answer, and a
    # subagent's own loop can see neither this list nor a sibling's results.
    dispatched: list[list[ToolCall]] = []
    for _step in range(MAX_TOOL_STEPS):
        calls: list[ToolCall] = []
        step_text: list[str] = []
        deltas = backend.stream(
            model, working, tools=specs, schema=context.schema, bounds=context.bounds
        )
        try:
            async for event in deltas:
                if isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, ReasoningChunk):
                    yield ReasoningDelta(event.text)
                else:
                    text = _reply_text(event, context)
                    if text is not None:
                        step_text.append(text)
                        yield text
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
            call_message("".join(step_text), plan.calls, context.clock.now(), context.unit_id)
        )
        round_events = run_round(plan, dispatcher, spec_by_name, dispatched, context, working)
        try:
            async for event in round_events:
                yield event
        finally:
            # Closed deterministically for the same reason the backend stream above is: a
            # consumer that closes this loop mid-round must not leave the round suspended
            # inside a dispatch.
            await round_events.aclose()
