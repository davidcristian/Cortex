"""The bounded infer↔tool loop, shared by the cortex turn and each subagent (ADR-0010/0013).

Both the cortex ``TurnEngine`` and a ``SubagentRunner`` do the same thing: stream from a model
with tools available; when the model emits tool calls, dispatch each through the audited
``ToolDispatcher`` and feed the results back; repeat until a final text answer or
``MAX_TOOL_STEPS``. That loop (inlined in ``handle_turn`` before Slice 7) lives here so both
callers reuse it verbatim: one loop, one bound, one audited dispatch path. The loop mutates the
``working`` message list in place (appending the tool-call and result messages) and yields each
assistant reply delta (a ``str``), any ``ReasoningDelta`` a reasoning model streams (ADR-0020),
and a ``ToolStep`` per audited dispatch (ADR-0009 addendum); the caller accumulates the reply
text and decides what to do with each (the cortex surfaces reasoning as status and tool steps
as activity, a subagent drops both).

The loop is also where the untrusted-content boundary is drawn (ADR-0013): an UNTRUSTED result
is fenced by ``wrap_untrusted`` before it re-enters the context, the per-turn ``TaintLedger``
observes every result, marking taint so a later gated call is confirmed, and collecting the
URLs untrusted content carried so the output guardrail can redact a laundered one (ADR-0015)
and the ledger + nonce ride in the ``ToolLoopContext`` bundle (keeping the loop within its
argument ceiling). Both callers construct the ledger, so both accumulate taint by the same
mechanism.
"""

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from datetime import datetime

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.inference import JsonSchema, ReasoningChunk
from cortex_core.ports import Clock, InferenceBackend
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
    envelope; ``None`` for the cortex and every tool-enabled path). Both the cortex turn and
    each subagent build one per invocation.
    """

    dispatcher: ToolDispatcher | None
    clock: Clock
    turn_id: str
    taint: TaintLedger
    nonce: str
    session_id: str
    schema: JsonSchema | None = None


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

    The loop advertises exactly the tools it can dispatch: the dispatcher's tools when present,
    none otherwise. With ``dispatcher`` None (or once the model stops calling tools) the loop
    ends after one inference step. Each tool call is dispatched through the audited dispatcher, with
    gated calls confirmed against the turn's taint (ADR-0013). Its result marks the taint ledger
    and is fed back (fenced when untrusted) as a ``Role.TOOL`` message before re-inference.
    Reasoning deltas and tool steps are surfaced live but never join ``step_text``, so they are
    neither persisted with the assistant message nor fed back into the next step's context.
    """
    dispatcher = context.dispatcher
    specs = await dispatcher.describe_tools() if dispatcher is not None else ()
    gated_by_name = {spec.name: spec.gated for spec in specs}
    spec_by_name = {spec.name: spec for spec in specs}
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
            # Surface activity only for a call that matched an advertised spec, so the chip's
            # name and summary are both registry-authored (ADR-0009 addendum). A call to an
            # unadvertised name (a model hallucination, or a tool skip-mode hid) still
            # dispatches below and fails as its usual is_error result, but never renders a
            # chip carrying the model's chosen string.
            if (spec := spec_by_name.get(call.name)) is not None:
                yield ToolStep(tool_name=spec.name, summary=_step_summary(spec))
            # The advertised gated flag is a hint; the dispatcher OR-s it with its own
            # authoritative gated-name set, so a tool a flaky sidecar hid from this snapshot
            # (skip mode) and later recovered is still gated at dispatch (ADR-0022). The
            # stamp is built fresh per dispatch (ADR-0027): the taint bit is live and can
            # flip mid-loop as untrusted results arrive.
            result = await dispatcher.dispatch(
                call,
                stamp=TurnStamp(session_id=context.session_id, tainted=context.taint.tainted),
                gated=gated_by_name.get(call.name, False),
            )
            context.taint.observe(result)
            working.append(
                _result_message(result, context.clock.now(), context.turn_id, nonce=context.nonce)
            )
