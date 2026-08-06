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
from cortex_core.inference import InferenceEvent, JsonSchema

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

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools
        self.seen_schema = schema
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
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema
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
