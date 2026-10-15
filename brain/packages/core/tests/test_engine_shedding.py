import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CONTEXT_OVERFLOW_NOTE,
    MESSAGE_OVERFLOW_NOTE,
    UNREADABLE_CALL_NOTE,
    ContextOverflowError,
    EscalationSlot,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MalformedToolCallError,
    Message,
    RecordingAuditSink,
    Role,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
)
from cortex_core.shedding import SHED_CHARS_PER_TOKEN, shed_oldest_turns

_AT = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)

_ENGINE_LOGGER = "cortex_core.engine"


class _FixedClock:
    def now(self) -> datetime:
        return _AT


class _ContextBackend:
    """Refuses a prompt whose turns pass ``limit`` characters, one token a character."""

    def __init__(self, limit: int, *, counts: bool = True, malformed: bool = False) -> None:
        self._limit = limit
        self._counts = counts
        self._malformed = malformed
        self.requests: list[list[str]] = []

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
        self.requests.append([message.text for message in messages if message.role is Role.USER])
        size = sum(len(message.text) for message in messages if message.role is not Role.SYSTEM)
        if size > self._limit and self._malformed:
            msg = "the tool call arguments are not JSON"
            raise MalformedToolCallError(msg)
        if size > self._limit:
            msg = f"request ({size} tokens) exceeds the available context size ({self._limit})"
            raise ContextOverflowError(msg, excess=size - self._limit if self._counts else None)
        yield TextChunk("Yellow.")


async def _seed(store: InMemorySessionStore, turns: Sequence[tuple[str, str]]) -> None:
    for index, (user, reply) in enumerate(turns):
        turn_id = f"old-{index}"
        await store.append("s", Message(role=Role.USER, text=user, at=_AT, turn_id=turn_id))
        await store.append("s", Message(role=Role.ASSISTANT, text=reply, at=_AT, turn_id=turn_id))


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


async def test_a_refused_prompt_is_asked_again_without_the_old_turn_that_filled_it() -> None:
    store = InMemorySessionStore()
    await _seed(store, [("L" * 5000, "(too long)")])
    backend = _ContextBackend(2000)
    engine = TurnEngine(store, backend, _FixedClock())

    events = await _collect(engine.handle_turn("s", "What colour is a lemon?", turn_id="t-1"))

    assert events == [TextDelta("Yellow."), TurnCompleted(turn_id="t-1", full_text="Yellow.")]
    assert backend.requests == [
        ["L" * 5000, "What colour is a lemon?"],
        ["What colour is a lemon?"],
    ]
    stored = [message.text for message in await store.history("s")]
    assert stored == ["L" * 5000, "(too long)", "What colour is a lemon?", "Yellow."]


async def test_one_retry_drops_as_many_old_turns_as_the_stated_excess_needs() -> None:
    store = InMemorySessionStore()
    await _seed(store, [("a" * 300, "x"), ("b" * 300, "y"), ("c" * 300, "z")])
    backend = _ContextBackend(811)
    engine = TurnEngine(store, backend, _FixedClock())

    await _collect(engine.handle_turn("s", "and now?", turn_id="t-1"))

    assert len(backend.requests) == 2
    assert backend.requests[1] == ["c" * 300, "and now?"]


async def test_an_unstated_excess_drops_one_old_turn_a_retry() -> None:
    store = InMemorySessionStore()
    await _seed(store, [("a" * 300, "x"), ("b" * 300, "y"), ("c" * 300, "z")])
    backend = _ContextBackend(400, counts=False)
    engine = TurnEngine(store, backend, _FixedClock())

    events = await _collect(engine.handle_turn("s", "and now?", turn_id="t-1"))

    assert [len(request) for request in backend.requests] == [4, 3, 2]
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="Yellow.")


async def test_a_newest_message_too_long_alone_names_the_message_once_older_turns_are_gone() -> (
    None
):
    store = InMemorySessionStore()
    await _seed(store, [("short", "ok")])
    backend = _ContextBackend(100)
    engine = TurnEngine(store, backend, _FixedClock())

    events = await _collect(engine.handle_turn("s", "L" * 500, turn_id="t-1"))

    assert len(backend.requests) == 2
    assert events == [
        TextDelta(MESSAGE_OVERFLOW_NOTE),
        TurnCompleted(turn_id="t-1", full_text=MESSAGE_OVERFLOW_NOTE),
    ]


async def test_each_retry_is_logged_with_how_many_messages_it_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_ENGINE_LOGGER)
    store = InMemorySessionStore()
    await _seed(store, [("L" * 5000, "(too long)")])
    engine = TurnEngine(store, _ContextBackend(2000), _FixedClock())

    await _collect(engine.handle_turn("s", "lemon?", turn_id="t-1"))

    (record,) = [line for line in caplog.records if line.name == _ENGINE_LOGGER]
    assert "asking again without older turns" in record.getMessage()
    assert (record.__dict__["turn_id"], record.__dict__["dropped"]) == ("t-1", 2)
    assert not record.exc_info


async def test_an_escalation_after_a_retry_sees_the_prompt_that_was_sent() -> None:
    store = InMemorySessionStore()
    await _seed(store, [("L" * 5000, "(too long)")])
    slot = EscalationSlot()
    engine = TurnEngine(
        store, _ContextBackend(2000), _FixedClock(), capabilities=TurnCapabilities(escalation=slot)
    )

    await _collect(engine.handle_turn("s", "lemon?", turn_id="t-1"))

    assert slot.refs is not None
    assert slot.refs.base_len == len(slot.refs.working)
    assert "L" * 5000 not in [message.text for message in slot.refs.working]


async def test_an_unreadable_call_before_any_output_is_not_asked_again() -> None:
    store = InMemorySessionStore()
    await _seed(store, [("L" * 5000, "(too long)")])
    backend = _ContextBackend(2000, malformed=True)
    engine = TurnEngine(store, backend, _FixedClock())

    events = await _collect(engine.handle_turn("s", "lemon?", turn_id="t-1"))

    assert len(backend.requests) == 1
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text=UNREADABLE_CALL_NOTE)


class _CallThenRefuse:
    """Asks for one tool call, then refuses every later request as too long."""

    def __init__(self) -> None:
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
        if self.requests > 1:
            msg = "request (17000 tokens) exceeds the available context size (16384 tokens)"
            raise ContextOverflowError(msg, excess=616)
        yield ToolCall(id="c1", name="read", arguments={"path": "/big.log"})


async def test_a_refusal_after_a_tool_ran_ends_the_turn_rather_than_running_it_again() -> None:
    reads: list[object] = []

    async def read(arguments: Mapping[str, object]) -> str:
        reads.append(arguments["path"])
        return "a large file"

    spec = ToolSpec(name="read", description="read a file", parameters={"type": "object"})
    registry = InMemoryToolRegistry({"read": (spec, read)})
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    store = InMemorySessionStore()
    await _seed(store, [("an older question", "an older answer")])
    backend = _CallThenRefuse()
    engine = TurnEngine(
        store, backend, _FixedClock(), capabilities=TurnCapabilities(tools=dispatcher)
    )

    events = await _collect(engine.handle_turn("s", "read the log", turn_id="t-1"))

    assert (backend.requests, reads) == (2, ["/big.log"])
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text=CONTEXT_OVERFLOW_NOTE)


def _message(role: Role, text: str, turn_id: str) -> Message:
    return Message(role=role, text=text, at=_AT, turn_id=turn_id)


def test_shedding_keeps_every_system_message_and_the_newest_turn() -> None:
    working = [
        _message(Role.SYSTEM, "preamble", "t-3"),
        _message(Role.SYSTEM, "recap", "t-0"),
        _message(Role.USER, "first", "t-1"),
        _message(Role.ASSISTANT, "reply", "t-1"),
        _message(Role.USER, "newest", "t-3"),
    ]

    shed = shed_oldest_turns(working, None)

    assert shed is not None
    assert [message.text for message in shed] == ["preamble", "recap", "newest"]


def test_shedding_stops_once_the_dropped_text_covers_the_excess() -> None:
    working = [
        _message(Role.USER, "a" * 47, "t-1"),
        _message(Role.USER, "b" * 47, "t-2"),
        _message(Role.USER, "newest", "t-3"),
    ]

    shed = shed_oldest_turns(working, int(47 / SHED_CHARS_PER_TOKEN))

    assert shed is not None
    assert [message.text for message in shed] == ["b" * 47, "newest"]


def test_shedding_has_nothing_to_drop_when_only_the_newest_turn_is_left() -> None:
    working = [_message(Role.SYSTEM, "preamble", "t-1"), _message(Role.USER, "newest", "t-1")]

    assert shed_oldest_turns(working, 10) is None
