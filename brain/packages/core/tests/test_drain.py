"""Behavior of drain_text: one model call consumed to its end, its stream closed at a point.

What the helper guarantees (ADR-0038 decision 8) is that the adapter's ``async with
manager.acquire(...)`` block is left before the call returns, however the call ends: a stream still
suspended inside it holds the GPU lease, and the turn whose reply acquires next would wait on
nothing. These tests watch that block's ``finally`` run on the happy path and on a mid-stream
failure, and they pin the guard around ``aclose`` by draining a stream that has none.
"""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import InferenceError, Message, ReasoningChunk, Role, TextChunk, ToolCall, ToolSpec
from cortex_core.drain import drain_text
from cortex_core.inference import (
    DecodeStop,
    GenerationBounds,
    InferenceEvent,
    JsonSchema,
    StopReason,
)
from cortex_core.stops import StopLedger

_AT = datetime(2026, 8, 6, tzinfo=UTC)


def _message() -> Message:
    return Message(role=Role.USER, text="rank these", at=_AT, turn_id="t")


class _GeneratorBackend:
    """An InferenceBackend whose stream is a real async generator, so it has a ``finally``."""

    def __init__(self, events: Sequence[InferenceEvent], *, fail_after: int | None = None) -> None:
        self._events = events
        self._fail_after = fail_after
        self.closed = False
        self.seen_schema: JsonSchema | None = None
        self.seen_bounds: GenerationBounds | None = None

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        self.seen_schema = schema
        self.seen_bounds = bounds
        try:
            for index, event in enumerate(self._events):
                if self._fail_after is not None and index == self._fail_after:
                    msg = "llama-server died mid-stream"
                    raise InferenceError(msg)
                yield event
        finally:
            # Stands in for the adapter leaving its `async with manager.acquire(...)` block.
            self.closed = True


class _IteratorBackend:
    """An InferenceBackend whose stream is a plain async iterator: no ``aclose`` to call."""

    def __init__(self, events: Sequence[InferenceEvent]) -> None:
        self._events = events

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        return _PlainIterator(self._events)


class _PlainIterator:
    def __init__(self, events: Sequence[InferenceEvent]) -> None:
        self._remaining = list(events)

    def __aiter__(self) -> "_PlainIterator":
        return self

    async def __anext__(self) -> InferenceEvent:
        if not self._remaining:
            raise StopAsyncIteration
        return self._remaining.pop(0)


async def test_drain_joins_only_the_reply_text() -> None:
    backend = _GeneratorBackend(
        [
            ReasoningChunk("thinking out loud"),
            TextChunk("Green "),
            ToolCall(id="1", name="noop", arguments={}),
            TextChunk("Tea"),
        ]
    )
    assert await drain_text(backend, "cortex", [_message()]) == "Green Tea"
    assert backend.closed  # exhausted, so the lease is already released


async def test_drain_leaves_no_open_stream_when_the_model_fails_partway() -> None:
    """A failure propagates and the lease is not stranded behind a half-read stream."""
    backend = _GeneratorBackend([TextChunk("half an ans"), TextChunk("never")], fail_after=1)
    with pytest.raises(InferenceError):
        await drain_text(backend, "cortex", [_message()])
    assert backend.closed  # the acquire block is left, so the next acquire is not waiting on it


async def test_drain_passes_a_constraining_schema_through() -> None:
    schema: JsonSchema = {"type": "object", "properties": {}}
    backend = _GeneratorBackend([TextChunk("{}")])
    await drain_text(backend, "cortex", [_message()], schema=schema)
    assert backend.seen_schema == schema


async def test_drain_accepts_a_stream_that_is_not_a_generator() -> None:
    """A plain iterator has no suspended ``finally`` and so no ``aclose``; draining still works."""
    backend = _IteratorBackend([TextChunk("plain")])
    assert await drain_text(backend, "cortex", [_message()]) == "plain"


async def test_bounds_reach_the_backend_unchanged() -> None:
    """The helper is a pass-through for how far the call may go, not a policy about it.

    Every ``drain_text`` caller is an in-turn side call whose thinking this helper throws away
    a line later, which is exactly what makes a bound worth asking for here.
    """
    backend = _GeneratorBackend([TextChunk("an account.")])
    bounds = GenerationBounds(max_tokens=512, thinking=False)
    assert await drain_text(backend, "cortex", [_message()], bounds=bounds) == "an account."
    assert backend.seen_bounds == bounds


async def test_no_bounds_is_what_a_reply_still_asks_for() -> None:
    backend = _GeneratorBackend([TextChunk("hello")])
    await drain_text(backend, "cortex", [_message()])
    assert backend.seen_bounds is None


def test_bounds_default_to_the_deployments_own_settings() -> None:
    unbounded = GenerationBounds()
    assert unbounded.max_tokens is None
    assert unbounded.thinking is True


def test_a_cap_of_no_tokens_is_a_configuration_mistake_not_a_silent_empty_reply() -> None:
    # A zero or negative cap cannot produce an answer, so it fails where it is written rather
    # than as an empty account the window would report as the model saying nothing usable.
    with pytest.raises(ValueError, match="at least 1"):
        GenerationBounds(max_tokens=0)
    with pytest.raises(ValueError, match="at least 1"):
        GenerationBounds(max_tokens=-1)


async def test_a_capped_stop_reaches_the_ledger_a_caller_handed_in() -> None:
    """The optional collaborator, threaded the way the tool loop threads one.

    A ``DecodeStop`` says why the machine stopped, not what the model said, so it must reach the
    ledger and never the returned text. The text assertion is half the point: a stop that leaked
    into the join would put a machine fact into an account a user reads.
    """
    ledger = StopLedger()
    backend = _GeneratorBackend(
        [TextChunk("They agreed to ship on the"), DecodeStop(reason=StopReason.CAPPED)]
    )
    text = await drain_text(backend, "cortex", [_message()], stops=ledger)
    assert text == "They agreed to ship on the"
    assert ledger.capped is True


async def test_a_completion_that_ended_itself_leaves_the_ledger_uncapped() -> None:
    """The contrast that makes the flag mean something: same shape, opposite reading."""
    ledger = StopLedger()
    backend = _GeneratorBackend(
        [TextChunk("They agreed to ship on the"), DecodeStop(reason=StopReason.FINISHED)]
    )
    assert await drain_text(backend, "cortex", [_message()], stops=ledger) == (
        "They agreed to ship on the"
    )
    assert ledger.capped is False


async def test_a_stop_with_no_ledger_is_dropped_exactly_as_it_always_was() -> None:
    """The two callers that want only a string are untouched by the new keyword.

    A stop arriving with nowhere to go must be discarded silently, which is the behaviour this
    helper shipped before a ledger could be passed at all.
    """
    backend = _GeneratorBackend([TextChunk("a title"), DecodeStop(reason=StopReason.CAPPED)])
    assert await drain_text(backend, "cortex", [_message()]) == "a title"
    assert backend.closed


async def test_an_event_that_is_neither_text_nor_a_stop_is_dropped_with_a_ledger_watching() -> None:
    """The arm a ledger must not change: private thinking stays out of the text either way."""
    ledger = StopLedger()
    backend = _GeneratorBackend([ReasoningChunk("thinking out loud"), TextChunk("the answer")])
    assert await drain_text(backend, "cortex", [_message()], stops=ledger) == "the answer"
    assert ledger.capped is False
