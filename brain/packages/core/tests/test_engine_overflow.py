import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CONTEXT_OVERFLOW_NOTE,
    REPLY_CAPPED_NOTE,
    ContextOverflowError,
    DecodeStop,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryRecaller,
    Message,
    RecordingAuditSink,
    Role,
    StopReason,
    SystemClock,
    TextChunk,
    TextDelta,
    ToolActivity,
    ToolCall,
    ToolDispatcher,
    ToolOutcome,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
    UrlRedactingGuardrail,
)

_AT = datetime(2026, 9, 28, 4, 0, tzinfo=UTC)

_ENGINE_LOGGER = "cortex_core.engine"

_REFUSAL = "request (18274 tokens) exceeds the available context size (16384 tokens)"


class _FixedClock:
    def now(self) -> datetime:
        return _AT


class _OverflowingBackend:
    """Streams each scripted round in turn, then refuses the next request as too long."""

    def __init__(self, rounds: Sequence[Sequence[InferenceEvent]] = ()) -> None:
        self._rounds = [list(events) for events in rounds]
        self.requests = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        self.requests += 1
        if not self._rounds:
            raise ContextOverflowError(_REFUSAL)
        for event in self._rounds.pop(0):
            yield event


async def _read_handler(arguments: Mapping[str, object]) -> str:
    return f"contents of {arguments['path']}"


def _read_dispatcher() -> ToolDispatcher:
    spec = ToolSpec(name="read", description="read a file", parameters={"type": "object"})
    registry = InMemoryToolRegistry({"read": (spec, _read_handler)})
    return ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


async def test_a_prompt_longer_than_the_context_ends_the_turn_with_the_overflow_note() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, _OverflowingBackend(), _FixedClock())

    events = await _collect(engine.handle_turn("s", "summarize all of it", turn_id="t-1"))

    assert events == [
        TextDelta(CONTEXT_OVERFLOW_NOTE),
        TurnCompleted(turn_id="t-1", full_text=CONTEXT_OVERFLOW_NOTE),
    ]
    history = [(message.role, message.text) for message in await store.history("s")]
    assert history == [
        (Role.USER, "summarize all of it"),
        (Role.ASSISTANT, CONTEXT_OVERFLOW_NOTE),
    ]


async def test_an_overflow_after_a_capped_tool_round_gives_only_the_overflow_note() -> None:
    store = InMemorySessionStore()
    backend = _OverflowingBackend(
        [
            [
                TextChunk("checking... "),
                ToolCall(id="c1", name="read", arguments={"path": "/big.log"}),
                DecodeStop(StopReason.CAPPED),
            ]
        ]
    )
    engine = TurnEngine(
        store, backend, _FixedClock(), capabilities=TurnCapabilities(tools=_read_dispatcher())
    )

    events = await _collect(engine.handle_turn("s", "read the log", turn_id="t-1"))

    assert backend.requests == 2
    assert events == [
        TextDelta("checking... "),
        ToolActivity(tool_name="read", summary="read a file"),
        ToolOutcome(tool_name="read", ok=True),
        TextDelta(CONTEXT_OVERFLOW_NOTE),
        TurnCompleted(turn_id="t-1", full_text=f"checking... {CONTEXT_OVERFLOW_NOTE}"),
    ]
    stored = [message.text for message in await store.history("s")]
    assert stored[-1] == f"checking... {CONTEXT_OVERFLOW_NOTE}"
    assert REPLY_CAPPED_NOTE not in stored[-1]


async def test_a_guardrails_held_tail_is_released_before_the_overflow_note() -> None:
    store = InMemorySessionStore()
    backend = _OverflowingBackend(
        [[TextChunk("see http://exa"), ToolCall(id="c1", name="read", arguments={"path": "/a"})]]
    )
    engine = TurnEngine(
        store,
        backend,
        _FixedClock(),
        capabilities=TurnCapabilities(tools=_read_dispatcher(), guardrail=UrlRedactingGuardrail()),
    )

    events = await _collect(engine.handle_turn("s", "where is it", turn_id="t-1"))

    texts = [event.text for event in events if isinstance(event, TextDelta)]
    assert texts == ["see ", "http://exa", CONTEXT_OVERFLOW_NOTE]
    stored = [message.text for message in await store.history("s")]
    assert stored[-1] == f"see http://exa{CONTEXT_OVERFLOW_NOTE}"


async def test_an_overflowing_turn_still_records_the_exchange_to_memory() -> None:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    engine = TurnEngine(
        InMemorySessionStore(),
        _OverflowingBackend(),
        _FixedClock(),
        capabilities=TurnCapabilities(memory=recaller),
    )

    await _collect(engine.handle_turn("s", "remember this", turn_id="t-1"))

    (recalled,) = await recaller.recall("remember this", k=1, session_id="s", turn_id="t")
    assert CONTEXT_OVERFLOW_NOTE.strip() in recalled.record.text


async def test_the_operator_is_told_which_turn_outgrew_the_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_ENGINE_LOGGER)
    engine = TurnEngine(InMemorySessionStore(), _OverflowingBackend(), _FixedClock())

    await _collect(engine.handle_turn("s", "hello", turn_id="t-1"))

    (record,) = [line for line in caplog.records if line.name == _ENGINE_LOGGER]
    assert record.levelno == logging.WARNING
    assert "longer than the model's context" in record.getMessage()
    assert (record.__dict__["session_id"], record.__dict__["turn_id"]) == ("s", "t-1")
    assert record.exc_info is not None
    assert isinstance(record.exc_info[1], ContextOverflowError)
