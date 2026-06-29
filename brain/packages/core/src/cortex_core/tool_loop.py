"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010)."""

from collections.abc import AsyncGenerator, Sequence
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.tools import ToolCall, ToolResult

# Upper bound on inference↔tool rounds in one loop (ADR-0009): a safety net against a model
# that never stops calling tools. On exhaustion the loop ends with the text produced so far.
MAX_TOOL_STEPS = 8


def _call_message(text: str, calls: Sequence[ToolCall], at: datetime, turn_id: str) -> Message:
    """The assistant's tool-calling step, carrying its native ``tool_calls`` for re-inference."""
    return Message(role=Role.ASSISTANT, text=text, at=at, turn_id=turn_id, tool_calls=tuple(calls))


def _result_message(result: ToolResult, at: datetime, turn_id: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers."""
    return Message(
        role=Role.TOOL, text=result.content, at=at, turn_id=turn_id, tool_call_id=result.call_id
    )


async def stream_tool_loop(
    backend: InferenceBackend,
    model: str,
    working: list[Message],
    *,
    dispatcher: ToolDispatcher | None,
    clock: Clock,
    turn_id: str,
) -> AsyncGenerator[str, None]:
    """Run the bounded infer↔tool loop over ``working``, yielding assistant text deltas."""
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    for _step in range(MAX_TOOL_STEPS):
        calls: list[ToolCall] = []
        step_text: list[str] = []
        deltas = backend.stream(model, working, tools=specs)
        try:
            async for event in deltas:
                if isinstance(event, ToolCall):
                    calls.append(event)
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
        working.append(_call_message("".join(step_text), calls, clock.now(), turn_id))
        for call in calls:
            result = await dispatcher.dispatch(call)
            working.append(_result_message(result, clock.now(), turn_id))
