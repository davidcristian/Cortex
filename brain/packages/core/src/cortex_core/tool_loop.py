"""The bounded infer↔tool loop, shared by the cortex turn and each subagent."""

from collections.abc import AsyncGenerator

from cortex_core.conversation import Message
from cortex_core.dispatch_round import ToolLoopContext, run_round
from cortex_core.inference import DecodeCadence, DecodeStop, ReasoningChunk, TextChunk
from cortex_core.loop_events import ReasoningDelta, StepOutcome, ToolStep
from cortex_core.ports import InferenceBackend
from cortex_core.tool_round import call_message, plan_round
from cortex_core.tools import ToolCall

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


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding each delta, step and outcome."""
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    spec_by_name = {spec.name: spec for spec in specs}
    # Every call this loop has dispatched, grouped by the round that emitted it, which is what
    # the salience policy reads. Per loop rather than per turn: a repeat is redundant only
    # against the ``working`` messages that already hold its answer.
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
            # Runs on exhaustion, on a backend failure and when a consumer closes this loop, so
            # an abandoned backend stream is never left half-suspended.
            if isinstance(deltas, AsyncGenerator):
                await deltas.aclose()
        if not calls or dispatcher is None:
            break
        plan = plan_round(calls)
        working.append(
            call_message("".join(step_text), plan.calls, context.clock.now(), context.unit_id)
        )
        round_events = run_round(plan, dispatcher, spec_by_name, dispatched, context, working)
        try:
            async for event in round_events:
                yield event
        finally:
            await round_events.aclose()
