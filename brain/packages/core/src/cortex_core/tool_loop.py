"""The bounded infer↔tool loop, shared by the cortex turn and each subagent."""

from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence

from cortex_core.conversation import Message, Role
from cortex_core.dispatch_round import LoopRecord, ToolLoopContext, run_round
from cortex_core.errors import InferenceError
from cortex_core.forget_open import Exchange
from cortex_core.forget_unrequested import forget_unrequested
from cortex_core.inference import (
    DecodeCadence,
    DecodeStop,
    InferenceEvent,
    ReasoningChunk,
    TextChunk,
)
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.memory_forget import FORGET_UNTRUSTED_TOOL_NAME
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.ports import InferenceBackend
from cortex_core.progress import hold_wait
from cortex_core.reply_notes import model_text
from cortex_core.round_opening import OpeningHold
from cortex_core.tool_cut import ResultRoom
from cortex_core.tool_round import call_message, plan_round
from cortex_core.tool_skips import list_tools
from cortex_core.tool_steps import MAX_TOOL_STEPS
from cortex_core.tools import ToolCall, ToolSpec
from cortex_core.unasked_tools import unasked_forget, unasked_sidecar_tools, unasked_tools

__all__ = ["MAX_TOOL_STEPS", "ToolLoopContext", "stream_tool_loop"]

_FORGET_TOOLS = frozenset({FORGET_CHOSEN_TOOL_NAME, FORGET_UNTRUSTED_TOOL_NAME})


def _reply_text(
    event: TextChunk | DecodeCadence | DecodeStop, context: ToolLoopContext
) -> str | None:
    """The reply text in an event, or ``None`` once it has been absorbed as a machine fact."""
    if isinstance(event, DecodeCadence):
        if context.cadence is not None:
            context.cadence.observe(event)
        return None
    if isinstance(event, DecodeStop):
        if context.stops is not None:
            context.stops.observe(event)
        return None
    return event.text


def _report_round_limit(context: ToolLoopContext) -> None:
    """Tell the loop's ledger, when it has one, that its last round still ended in tool calls."""
    if context.stops is not None:
        context.stops.observe_round_limit()


async def _round_pieces(
    deltas: AsyncIterator[InferenceEvent],
    context: ToolLoopContext,
    opening: OpeningHold,
    calls: list[ToolCall],
) -> AsyncGenerator[str | ReasoningDelta, None]:
    """One round's streamed reply text and reasoning; its tool calls go into ``calls``."""
    try:
        async with hold_wait(context.progress, context.generating):
            async for event in deltas:
                if isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, ReasoningChunk):
                    yield ReasoningDelta(event.text)
                elif shown := opening.feed(_reply_text(event, context) or ""):
                    yield shown
    except InferenceError:
        if held := opening.flush():
            yield held
        raise
    finally:
        # Runs on exhaustion, on a backend failure and when a consumer closes this loop, so
        # an abandoned backend stream is never left half-suspended.
        if isinstance(deltas, AsyncGenerator):
            await deltas.aclose()
    if held := opening.flush():
        yield held


def _earlier(working: Sequence[Message], turn_id: str) -> list[Message]:
    """``working`` latest first, less the messages of the turn ``turn_id``."""
    # A handoff's working list ends with the cortex's calls for this turn, after its message.
    return [message for message in reversed(working) if message.turn_id != turn_id]


def _last_reply(working: Sequence[Message], turn_id: str) -> str:
    """The text of the last assistant message before the turn ``turn_id``, empty when none."""
    return next((m.text for m in _earlier(working, turn_id) if m.role is Role.ASSISTANT), "")


def _exchange(turn: Sequence[Message]) -> Exchange | None:
    """One earlier turn's messages, oldest first, as an exchange, or ``None`` with no reply."""
    replies = [message for message in turn if message.role is Role.ASSISTANT]
    if not replies:
        return None
    ask = next((m.text for m in turn if m.role is Role.USER), "")
    forgot = any(run.name in _FORGET_TOOLS for reply in replies for run in reply.runs)
    return Exchange(ask, model_text(replies[-1].text), forgot=forgot)


def _earlier_exchanges(working: Sequence[Message], turn_id: str) -> tuple[Exchange, ...]:
    """The last two exchanges before the turn ``turn_id`` that stored a reply, latest first."""
    turns: dict[str, list[Message]] = {}
    for message in _earlier(working, turn_id):
        turns.setdefault(message.turn_id, []).insert(0, message)
    exchanges = (_exchange(turn) for turn in turns.values())
    return tuple(exchange for exchange in exchanges if exchange is not None)[:2]


async def _turn_tools(
    context: ToolLoopContext, working: Sequence[Message]
) -> tuple[Sequence[ToolSpec], Mapping[str, ToolSpec], frozenset[str], frozenset[str]]:
    """The tools offered, every listed spec by name, those refused by name, and the unrequested."""
    if context.dispatcher is None:
        return (), {}, frozenset(), frozenset()
    specs = await list_tools(context.dispatcher, context.progress)
    left_out = unasked_tools(context.query)
    withheld = await context.dispatcher.withheld(context.session_id) | left_out
    # A withheld tool keeps its spec here, so a call to it by name still shows its card or, for
    # an unasked tool, its refusal. A sidecar tool stays listed, since a shorter list raised the
    # model's forget calls in one of two comparisons (unasked-tools-listed-on-remember.md).
    offered = tuple(spec for spec in specs if spec.name not in withheld)
    last_reply = _last_reply(working, context.turn_id)
    forget = unasked_forget(context.query, last_reply)
    earlier = _earlier_exchanges(working, context.turn_id)
    unrequested = forget_unrequested(context.query, earlier) - forget
    refused = left_out | unasked_sidecar_tools(context.query, specs) | forget | unrequested
    return offered, {s.name: s for s in specs}, refused, unrequested


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding each delta, step and outcome."""
    dispatcher = context.dispatcher
    specs, spec_by_name, unasked, unrequested = await _turn_tools(context, working)
    # Per loop rather than per turn: a repeat is redundant only against the ``working`` messages
    # that already hold its answer, and the results share the room of that one request.
    record = LoopRecord(
        room=ResultRoom(context.room_chars, spent=context.results_spent),
        unasked=unasked,
        unrequested=unrequested,
        yearly_refused=list(context.yearly_refused),
        midnight_refused=list(context.midnight_refused),
        weekly_refused=list(context.weekly_refused),
        offset_refused=list(context.offset_refused),
    )
    said: list[str] = []
    for _step in range(MAX_TOOL_STEPS):
        calls: list[ToolCall] = []
        step_text: list[str] = []
        deltas = backend.stream(
            model, working, tools=specs, schema=context.schema, bounds=context.bounds
        )
        # The model can open a round after a call with the sentence it wrote before the call.
        pieces = _round_pieces(deltas, context, OpeningHold("".join(said)), calls)
        try:
            async for piece in pieces:
                if isinstance(piece, str):
                    step_text.append(piece)
                yield piece
        finally:
            await pieces.aclose()
        said.extend(step_text)
        # Before any refusal or the round's cut, so a call that never runs still marks the turn,
        # unless the person's message cannot have asked for it.
        if FORGET_CHOSEN_TOOL_NAME not in unasked:
            context.taint.name_forget(sum(call.name == FORGET_CHOSEN_TOOL_NAME for call in calls))
        if not calls or dispatcher is None:
            break
        plan = plan_round(calls)
        working.append(
            call_message("".join(step_text), plan.calls, context.clock.now(), context.unit_id)
        )
        round_events = run_round(plan, dispatcher, spec_by_name, record, context, working)
        try:
            async for event in round_events:
                yield event
        finally:
            await round_events.aclose()
    else:
        _report_round_limit(context)
