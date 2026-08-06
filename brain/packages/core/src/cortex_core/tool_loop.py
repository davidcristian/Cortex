"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013)."""

from collections.abc import AsyncGenerator

from cortex_core.conversation import Message
from cortex_core.dispatch_round import ToolLoopContext, run_round
from cortex_core.inference import ReasoningChunk
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


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    context: ToolLoopContext,
) -> AsyncGenerator[str | ReasoningDelta | ToolStep | StepOutcome, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding reply-text deltas (``str``),
    reasoning deltas (``ReasoningDelta``, ADR-0020), a ``ToolStep`` per audited dispatch
    (ADR-0009 addendum), and the ``StepOutcome`` that settles it (ADR-0029 outcome addendum).
    """
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    spec_by_name = {spec.name: spec for spec in specs}
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
        round_events = run_round(plan, dispatcher, spec_by_name, dispatched, context, working)
        try:
            async for event in round_events:
                yield event
        finally:
            # Closed deterministically for the same reason the backend stream above is: a
            # consumer that closes this loop mid-round must not leave the round suspended
            # inside a dispatch.
            await round_events.aclose()
