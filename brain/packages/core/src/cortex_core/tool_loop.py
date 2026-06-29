"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010).

Both the cortex ``TurnEngine`` and a ``SubagentRunner`` do the same thing: stream from a model
with tools available; when the model emits tool calls, dispatch each through the audited
``ToolDispatcher`` and feed the results back; repeat until a final text answer or
``MAX_TOOL_STEPS``. That loop (inlined in ``handle_turn`` before Slice 7) lives here so both
callers reuse it verbatim: one loop, one bound, one audited dispatch path. The loop mutates the
``working`` message list in place (appending the tool-call and result messages) and yields each
assistant text delta; the caller accumulates the full answer and decides what to do with deltas.
"""

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
    """Run the bounded infer↔tool loop over ``working``, yielding assistant text deltas.

    The loop advertises exactly the tools it can dispatch: the dispatcher's tools when present,
    none otherwise. With ``dispatcher`` None (or once the model stops calling tools) the loop
    ends after one inference step. Each tool call is dispatched through the audited dispatcher
    and its result fed back as a ``Role.TOOL`` message before re-inference.
    """
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
