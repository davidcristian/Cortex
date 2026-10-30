"""The bounded infer↔tool loop, shared by the cortex turn and each subagent."""

from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence

from cortex_core.conversation import Message
from cortex_core.dispatch_round import LoopRecord, ToolLoopContext, run_round
from cortex_core.errors import InferenceError
from cortex_core.inference import (
    DecodeCadence,
    DecodeStop,
    InferenceEvent,
    ReasoningChunk,
    TextChunk,
)
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.memory_forget_chosen import FORGET_CHOSEN_TOOL_NAME
from cortex_core.ports import InferenceBackend
from cortex_core.progress import hold_wait
from cortex_core.round_opening import OpeningHold
from cortex_core.tool_cut import ResultRoom
from cortex_core.tool_round import call_message, plan_round
from cortex_core.tool_skips import list_tools
from cortex_core.tools import ToolCall, ToolSpec

__all__ = ["MAX_TOOL_STEPS", "ToolLoopContext", "stream_tool_loop"]

MAX_TOOL_STEPS = 8


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


async def _turn_tools(
    context: ToolLoopContext,
) -> tuple[Sequence[ToolSpec], Mapping[str, ToolSpec]]:
    """The tools offered to the model, and every listed spec by name to read its calls with."""
    if context.dispatcher is None:
        return (), {}
    specs = await list_tools(context.dispatcher, context.progress)
    withheld = await context.dispatcher.withheld(context.session_id) | context.unasked
    # A withheld tool keeps its spec here, so a call to it by name still shows its card or, for
    # an unasked tool, its refusal.
    return tuple(spec for spec in specs if spec.name not in withheld), {s.name: s for s in specs}


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding each delta, step and outcome."""
    dispatcher = context.dispatcher
    specs, spec_by_name = await _turn_tools(context)
    # Per loop rather than per turn: a repeat is redundant only against the ``working`` messages
    # that already hold its answer, and the results share the room of that one request.
    record = LoopRecord(room=ResultRoom(context.room_chars, spent=context.results_spent))
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
        # Before any refusal or the round's cut, so a call that never runs still marks the turn.
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
