from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    GenerationBounds,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    ReasoningChunk,
    RecordingAuditSink,
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)
from cortex_core.loop_events import ReasoningDelta
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
_CALL = ToolCall(id="c1", name="noop", arguments={})


class _ThinkingBackend:
    """Thinks, then calls ``noop`` on the first round; thinks again, then answers, on the next."""

    def __init__(self, rounds: Sequence[Sequence[InferenceEvent]]) -> None:
        self._rounds = list(rounds)
        self.seen: list[list[Message]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(list(messages))
        for event in self._rounds[len(self.seen) - 1]:
            yield event


def _two_rounds() -> _ThinkingBackend:
    return _ThinkingBackend(
        [
            [
                ReasoningChunk("The list "),
                ReasoningChunk("comes first."),
                TextChunk("One moment. "),
                _CALL,
            ],
            [ReasoningChunk("It is empty."), TextChunk("You have none.")],
        ]
    )


async def _noop(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


def _context(bounds: GenerationBounds | None) -> ToolLoopContext:
    spec = ToolSpec(name="noop", description="do nothing", parameters={})
    clock = SystemClock()
    return ToolLoopContext(
        dispatcher=ToolDispatcher(
            InMemoryToolRegistry({"noop": (spec, _noop)}), RecordingAuditSink(), clock
        ),
        clock=clock,
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        bounds=bounds,
    )


async def _run(
    backend: _ThinkingBackend, bounds: GenerationBounds | None
) -> tuple[list[Message], Sequence[object]]:
    working = [Message(role=Role.USER, text="List my reminders.", at=_AT, turn_id="t-1")]
    pieces = [piece async for piece in stream_tool_loop(backend, "m", working, _context(bounds))]
    return working, pieces


def _call_messages(messages: Sequence[Message]) -> list[Message]:
    return [message for message in messages if message.tool_calls]


async def test_with_the_setting_on_the_round_s_trace_is_kept_on_its_call_message() -> None:
    backend = _two_rounds()
    working, _ = await _run(backend, GenerationBounds(resend_trace=True))
    (kept,) = _call_messages(working)
    assert (kept.text, kept.trace, kept.tool_calls) == (
        "One moment. ",
        "The list comes first.",
        (_CALL,),
    )


async def test_the_next_round_of_the_same_turn_is_sent_the_kept_trace() -> None:
    backend = _two_rounds()
    await _run(backend, GenerationBounds(resend_trace=True))
    first, second = backend.seen
    assert _call_messages(first) == []
    assert [message.trace for message in _call_messages(second)] == ["The list comes first."]


async def test_the_final_round_s_trace_is_kept_on_no_message() -> None:
    backend = _two_rounds()
    working, _ = await _run(backend, GenerationBounds(resend_trace=True))
    assert all("It is empty." not in message.trace for message in working)


@pytest.mark.parametrize(
    "bounds", [None, GenerationBounds(), GenerationBounds(max_tokens=512, thinking=False)]
)
async def test_with_the_setting_off_no_trace_is_kept(bounds: GenerationBounds | None) -> None:
    backend = _two_rounds()
    working, _ = await _run(backend, bounds)
    (kept,) = _call_messages(working)
    assert kept.trace == ""
    assert [message.trace for message in _call_messages(backend.seen[1])] == [""]


@pytest.mark.parametrize("bounds", [GenerationBounds(resend_trace=True), GenerationBounds()])
async def test_the_overlay_is_streamed_every_trace_whether_or_not_it_is_kept(
    bounds: GenerationBounds,
) -> None:
    _, pieces = await _run(_two_rounds(), bounds)
    shown = [piece.text for piece in pieces if isinstance(piece, ReasoningDelta)]
    assert shown == ["The list ", "comes first.", "It is empty."]


async def test_a_round_that_calls_without_thinking_keeps_an_empty_trace() -> None:
    backend = _ThinkingBackend([[_CALL], [TextChunk("Done.")]])
    working, _ = await _run(backend, GenerationBounds(resend_trace=True))
    (kept,) = _call_messages(working)
    assert kept.trace == ""
