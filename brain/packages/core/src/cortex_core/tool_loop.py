"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013)."""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.inference import JsonSchema, ReasoningChunk
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.tool_budget import MAX_TOOL_DISPATCHES
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust, TurnStamp
from cortex_core.untrusted import TaintLedger, wrap_untrusted

# Upper bound on inference↔tool rounds in one loop (ADR-0009): a safety net against a model
# that never stops calling tools. On exhaustion the loop ends with the text produced so far.
MAX_TOOL_STEPS = 8

# Upper bound on a ToolStep summary: the chip is one slim line, and an advertised description
# is sidecar-authored text of arbitrary length (ADR-0009 addendum).
MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A delta of the model's reasoning trace, surfaced by the loop distinctly from reply text
    (ADR-0020).
    """

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded by the loop immediately before the dispatch
    so a consumer can surface it while the tool works (ADR-0009 addendum).
    """

    tool_name: str
    summary: str


def _step_summary(spec: ToolSpec) -> str:
    """The chip text for one dispatch: the advertised description's first line, capped, with
    the advertised name as the fallback when the description is empty.
    """
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]


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
    dispatch_budget: int = MAX_TOOL_DISPATCHES


def _call_message(text: str, calls: Sequence[ToolCall], at: datetime, turn_id: str) -> Message:
    """The assistant's tool-calling step, carrying its native ``tool_calls`` for re-inference."""
    return Message(role=Role.ASSISTANT, text=text, at=at, turn_id=turn_id, tool_calls=tuple(calls))


def _result_message(result: ToolResult, at: datetime, turn_id: str, *, nonce: str) -> Message:
    """One tool result fed back to the model, keyed to the call it answers.

    UNTRUSTED content is fenced as inert data (ADR-0013); TRUSTED content passes through verbatim.
    """
    text = (
        result.content
        if result.trust is Trust.TRUSTED
        else wrap_untrusted(result.content, nonce=nonce)
    )
    return Message(role=Role.TOOL, text=text, at=at, turn_id=turn_id, tool_call_id=result.call_id)


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
    spent = 0
    budget_closed = False
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
        working.append(
            _call_message("".join(step_text), calls, context.clock.now(), context.turn_id)
        )
        for call in calls:
            cost = dispatcher.cost_of(call.name)
            budget_closed = budget_closed or spent + cost > context.dispatch_budget
            if not budget_closed:
                spent += cost
                if (spec := spec_by_name.get(call.name)) is not None:
                    yield ToolStep(tool_name=spec.name, summary=_step_summary(spec))
            result = await dispatcher.dispatch(
                call,
                stamp=TurnStamp(session_id=context.session_id, tainted=context.taint.tainted),
                gated=gated_by_name.get(call.name, False),
                over_budget=budget_closed,
            )
            context.taint.observe(result)
            working.append(
                _result_message(result, context.clock.now(), context.turn_id, nonce=context.nonce)
            )
