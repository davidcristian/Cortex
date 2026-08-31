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
    assert backend.closed


async def test_drain_leaves_no_open_stream_when_the_model_fails_partway() -> None:
    backend = _GeneratorBackend([TextChunk("half an ans"), TextChunk("never")], fail_after=1)
    with pytest.raises(InferenceError):
        await drain_text(backend, "cortex", [_message()])
    assert backend.closed


async def test_drain_passes_a_constraining_schema_through() -> None:
    schema: JsonSchema = {"type": "object", "properties": {}}
    backend = _GeneratorBackend([TextChunk("{}")])
    await drain_text(backend, "cortex", [_message()], schema=schema)
    assert backend.seen_schema == schema


async def test_drain_accepts_a_stream_that_is_not_a_generator() -> None:
    backend = _IteratorBackend([TextChunk("plain")])
    assert await drain_text(backend, "cortex", [_message()]) == "plain"


async def test_bounds_reach_the_backend_unchanged() -> None:
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
    assert GenerationBounds(trace_tokens=0).trace_tokens == 0
    with pytest.raises(ValueError, match="trace_tokens must not be negative"):
        GenerationBounds(trace_tokens=-1)


def test_a_cap_of_no_tokens_is_a_configuration_mistake_not_a_silent_empty_reply() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        GenerationBounds(max_tokens=0)
    with pytest.raises(ValueError, match="at least 1"):
        GenerationBounds(max_tokens=-1)


async def test_a_capped_stop_reaches_the_ledger_a_caller_handed_in() -> None:
    ledger = StopLedger()
    backend = _GeneratorBackend(
        [TextChunk("They agreed to ship on the"), DecodeStop(reason=StopReason.CAPPED)]
    )
    text = await drain_text(backend, "cortex", [_message()], stops=ledger)
    assert text == "They agreed to ship on the"
    assert ledger.capped is True


async def test_a_completion_that_ended_itself_leaves_the_ledger_uncapped() -> None:
    ledger = StopLedger()
    backend = _GeneratorBackend(
        [TextChunk("They agreed to ship on the"), DecodeStop(reason=StopReason.FINISHED)]
    )
    assert await drain_text(backend, "cortex", [_message()], stops=ledger) == (
        "They agreed to ship on the"
    )
    assert ledger.capped is False


async def test_a_stop_with_no_ledger_is_dropped_exactly_as_it_always_was() -> None:
    backend = _GeneratorBackend([TextChunk("a title"), DecodeStop(reason=StopReason.CAPPED)])
    assert await drain_text(backend, "cortex", [_message()]) == "a title"
    assert backend.closed


async def test_an_event_that_is_neither_text_nor_a_stop_is_dropped_with_a_ledger_watching() -> None:
    ledger = StopLedger()
    backend = _GeneratorBackend([ReasoningChunk("thinking out loud"), TextChunk("the answer")])
    assert await drain_text(backend, "cortex", [_message()], stops=ledger) == "the answer"
    assert ledger.capped is False


def _unread(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Every line this module logged about a reasoning trace it dropped."""
    return [record for record in caplog.records if record.name == _DRAIN_LOGGER]


async def _drained(
    caplog: pytest.LogCaptureFixture,
    events: Sequence[InferenceEvent],
    bounds: GenerationBounds | None,
) -> tuple[str, list[logging.LogRecord]]:
    """One drain, plus the lines it logged about the reasoning it dropped."""
    caplog.clear()
    caplog.set_level(logging.WARNING, logger=_DRAIN_LOGGER)
    text = await drain_text(_GeneratorBackend(events), "cortex", [_message()], bounds=bounds)
    return text, _unread(caplog)


async def test_a_trace_arriving_despite_the_switch_is_reported_with_what_it_cost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text, records = await _drained(
        caplog,
        [ReasoningChunk("first I should"), ReasoningChunk(" consider"), TextChunk("Green Tea")],
        GenerationBounds(max_tokens=32, thinking=False),
    )
    assert text == "Green Tea", "the reply must be returned exactly as it was"
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].__dict__["model"] == "cortex"
    assert records[0].__dict__["chars"] == len("first I should consider")


async def test_a_switch_the_deployment_honoured_says_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text, records = await _drained(
        caplog, [TextChunk("Green Tea")], GenerationBounds(max_tokens=32, thinking=False)
    )
    assert text == "Green Tea"
    assert records == []


async def test_a_trace_nobody_asked_against_is_dropped_as_quietly_as_ever(
    caplog: pytest.LogCaptureFixture,
) -> None:
    trace = [ReasoningChunk("thinking out loud"), TextChunk("a title")]
    _, thinking_on = await _drained(caplog, trace, GenerationBounds(max_tokens=32))
    _, unbounded = await _drained(caplog, trace, None)
    assert thinking_on == []
    assert unbounded == []


async def test_a_completion_that_failed_partway_describes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.clear()
    caplog.set_level(logging.WARNING, logger=_DRAIN_LOGGER)
    backend = _GeneratorBackend([ReasoningChunk("first I should"), TextChunk("x")], fail_after=1)
    with pytest.raises(InferenceError):
        await drain_text(backend, "cortex", [_message()], bounds=GenerationBounds(thinking=False))
    assert _unread(caplog) == []
