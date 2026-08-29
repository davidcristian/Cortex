"""Behavior of drain_text: one model call consumed to its end, its stream closed at a point.

What the helper guarantees (ADR-0038 decision 8) is that the adapter's ``async with
manager.acquire(...)`` block is left before the call returns, however the call ends: a stream still
suspended inside it holds the GPU lease, and the turn whose reply acquires next would wait on
nothing. These tests watch that block's ``finally`` run on the happy path and on a mid-stream
failure, and they pin the guard around ``aclose`` by draining a stream that has none.
"""

import logging
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
# The logger the helper writes its one warning under, named here so a check reads that module's own
# lines rather than whatever else a suite happened to log.
_DRAIN_LOGGER = "cortex_core.drain"


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
    assert unbounded.trace_tokens is None


def test_a_negative_trace_budget_is_refused_because_the_port_has_no_word_for_unrestricted() -> None:
    """``None`` already says "leave it to the tier", so no negative can mean it too.

    llama.cpp spells unrestricted `-1` on its own flag, and letting that sentinel through here
    would give the port two ways to say one thing and a caller two things to get right (ADR-0005
    request-lever addendum). Zero stays a real setting, which is why it is not refused beside it.
    """
    assert GenerationBounds(trace_tokens=0).trace_tokens == 0
    with pytest.raises(ValueError, match="trace_tokens must not be negative"):
        GenerationBounds(trace_tokens=-1)


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


def _unread(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Every line this module wrote about a trace it dropped unread."""
    return [record for record in caplog.records if record.name == _DRAIN_LOGGER]


async def _drained(
    caplog: pytest.LogCaptureFixture,
    events: Sequence[InferenceEvent],
    bounds: GenerationBounds | None,
) -> tuple[str, list[logging.LogRecord]]:
    """One drain, and whatever it said about the deliberation it was handed."""
    caplog.clear()
    caplog.set_level(logging.WARNING, logger=_DRAIN_LOGGER)
    text = await drain_text(_GeneratorBackend(events), "cortex", [_message()], bounds=bounds)
    return text, _unread(caplog)


async def test_a_trace_arriving_despite_the_switch_is_reported_with_what_it_cost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The deployment ignored the switch, so the drop is announced instead of silent.

    This is the failure the line exists for (ADR-0005 switch-is-advisory addendum): the caller
    paired a cap with a switch the template did not honour, so the model is spending that cap on a
    trace nobody will read and the reply arrives short or empty. ``chars`` is what makes the line
    a diagnosis rather than a hint, since the tokens are gone by the time anyone reads it.
    """
    text, records = await _drained(
        caplog,
        [ReasoningChunk("first I should"), ReasoningChunk(" consider"), TextChunk("Green Tea")],
        GenerationBounds(max_tokens=32, thinking=False),
    )
    assert text == "Green Tea", "the reply must be returned exactly as it was"
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    # ``extra`` lands in the record's own dict, which is where a formatter reads it from.
    assert records[0].__dict__["model"] == "cortex"
    assert records[0].__dict__["chars"] == len("first I should consider")


async def test_a_switch_the_deployment_honoured_says_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ordinary case, and the reason a line here means the one thing.

    A tier that skipped its deliberation, or one whose trace its own ``--reasoning-budget`` ended
    at once, streams no reasoning at all, so nothing is dropped and nothing is said.
    """
    text, records = await _drained(
        caplog, [TextChunk("Green Tea")], GenerationBounds(max_tokens=32, thinking=False)
    )
    assert text == "Green Tea"
    assert records == []


async def test_a_trace_nobody_asked_against_is_dropped_as_quietly_as_ever(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both ways of not asking: bounds that left thinking on, and no bounds at all.

    Every ``drain_text`` caller discards deliberation by construction, so a trace here is unread
    whatever the request said. What makes it worth a line is only that the request asked against
    it, and these two did not.
    """
    trace = [ReasoningChunk("thinking out loud"), TextChunk("a title")]
    _, thinking_on = await _drained(caplog, trace, GenerationBounds(max_tokens=32))
    _, unbounded = await _drained(caplog, trace, None)
    assert thinking_on == []
    assert unbounded == []


async def test_a_completion_that_failed_partway_describes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stream that died mid-trace says nothing, there being no completion to describe.

    The same stance the rank's two warnings take: a backend that could not answer is reported by
    the caller that catches ``InferenceError``, and reading a partial trace as a deployment
    ignoring the switch would blame a template for a dead server.
    """
    caplog.clear()
    caplog.set_level(logging.WARNING, logger=_DRAIN_LOGGER)
    backend = _GeneratorBackend([ReasoningChunk("first I should"), TextChunk("x")], fail_after=1)
    with pytest.raises(InferenceError):
        await drain_text(backend, "cortex", [_message()], bounds=GenerationBounds(thinking=False))
    assert _unread(caplog) == []
