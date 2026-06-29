"""Behavior tests for TurnEngine: event contract, persistence, cancellation, failure."""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from cortex_core import (
    DEFAULT_CORTEX_MODEL,
    EchoInferenceBackend,
    InferenceError,
    InMemorySessionStore,
    Message,
    Role,
    SystemClock,
    TextDelta,
    TurnCompleted,
    TurnEngine,
    TurnEvent,
)

_START = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class TickingClock:
    """Deterministic clock: each now() is one second after the previous one."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        at = _START + timedelta(seconds=self._ticks)
        self._ticks += 1
        return at


class RecordingBackend:
    """Async-generator backend that records calls and whether it was closed."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas
        self.calls: list[tuple[str, tuple[Message, ...]]] = []
        self.closed = False

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        self.calls.append((model, tuple(messages)))
        try:
            for delta in self._deltas:
                yield delta
        finally:
            self.closed = True


class _PlainDeltas:
    """An AsyncIterator that is NOT an AsyncGenerator (nothing to aclose)."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._pending = list(deltas)

    def __aiter__(self) -> "_PlainDeltas":
        return self

    async def __anext__(self) -> str:
        if not self._pending:
            raise StopAsyncIteration
        return self._pending.pop(0)


class PlainIteratorBackend:
    """Backend whose stream lacks aclose(); the engine must cope."""

    def __init__(self, deltas: Sequence[str]) -> None:
        self._deltas = deltas

    def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        return _PlainDeltas(self._deltas)


class MidStreamFailingBackend:
    """Backend that yields one delta and then fails with the typed error."""

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        yield "partial "
        msg = "backend exploded mid-stream"
        raise InferenceError(msg)


def _sequential_turn_ids() -> "list[str]":
    return [f"t-{n}" for n in range(1, 10)]


async def _collect(events: AsyncIterator[TurnEvent]) -> list[TurnEvent]:
    return [event async for event in events]


async def test_turn_streams_deltas_then_completion() -> None:
    store = InMemorySessionStore()
    ids = _sequential_turn_ids()
    engine = TurnEngine(
        store, EchoInferenceBackend(), TickingClock(), turn_id_factory=lambda: ids.pop(0)
    )
    events = await _collect(engine.handle_turn("s", "hello"))
    assert events == [
        TextDelta("reply "),
        TextDelta("1:"),
        TextDelta(" hello"),
        TurnCompleted(turn_id="t-1", full_text="reply 1: hello"),
    ]


async def test_turn_persists_user_then_assistant_with_shared_turn_id() -> None:
    store = InMemorySessionStore()
    clock = TickingClock()
    ids = _sequential_turn_ids()
    engine = TurnEngine(store, EchoInferenceBackend(), clock, turn_id_factory=lambda: ids.pop(0))
    await _collect(engine.handle_turn("s", "hello"))
    history = list(await store.history("s"))
    assert history == [
        Message(role=Role.USER, text="hello", at=_START, turn_id="t-1"),
        Message(
            role=Role.ASSISTANT,
            text="reply 1: hello",
            at=_START + timedelta(seconds=1),
            turn_id="t-1",
        ),
    ]


async def test_reply_counter_comes_from_the_store_not_the_engine() -> None:
    store = InMemorySessionStore()
    first_engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    await _collect(first_engine.handle_turn("s", "one"))
    # A brand-new engine over the same store keeps counting: no state in the engine.
    replacement = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    events = await _collect(replacement.handle_turn("s", "two"))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == "reply 2: two"


async def test_history_is_read_from_the_store_not_hidden_engine_state() -> None:
    """Seed turn 1 OUT-OF-BAND (never through any engine): the read path must hit the store.

    Any implementation that answers from hidden in-process state (e.g. a module-global
    history cache) has never seen turn 1 and would reply "reply 1: two". This test
    exists to kill exactly that mutant, which the restart-style tests cannot see.
    """
    store = InMemorySessionStore()
    await store.append("s", Message(role=Role.USER, text="one", at=_START, turn_id="t-0"))
    await store.append(
        "s", Message(role=Role.ASSISTANT, text="reply 1: one", at=_START, turn_id="t-0")
    )
    engine = TurnEngine(store, EchoInferenceBackend(), TickingClock())
    events = await _collect(engine.handle_turn("s", "two"))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == "reply 2: two"
    # Seed AGAIN between two turns of the SAME engine: every turn re-reads the
    # store, so a read-once-then-cache implementation dies here too.
    await store.append("s", Message(role=Role.USER, text="three", at=_START, turn_id="t-9"))
    await store.append(
        "s", Message(role=Role.ASSISTANT, text="reply 3: three", at=_START, turn_id="t-9")
    )
    events = await _collect(engine.handle_turn("s", "four"))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert completed.full_text == "reply 4: four"


async def test_backend_receives_model_id_and_full_history() -> None:
    store = InMemorySessionStore()
    backend = RecordingBackend(("a", "b", "c"))
    engine = TurnEngine(store, backend, TickingClock(), cortex_model="cortex-q4")
    await _collect(engine.handle_turn("s", "first"))
    await _collect(engine.handle_turn("s", "second"))
    assert [model for model, _ in backend.calls] == ["cortex-q4", "cortex-q4"]
    first_history, second_history = (messages for _, messages in backend.calls)
    assert [m.text for m in first_history] == ["first"]
    assert [m.text for m in second_history] == ["first", "abc", "second"]


async def test_default_model_and_turn_ids_are_uuid4_cortex() -> None:
    backend = RecordingBackend(("a", "b", "c"))
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock())
    events = await _collect(engine.handle_turn("s", "hi"))
    completed = events[-1]
    assert isinstance(completed, TurnCompleted)
    assert UUID(completed.turn_id).version == 4
    assert backend.calls[0][0] == DEFAULT_CORTEX_MODEL


async def test_aclose_mid_generation_keeps_user_and_drops_partial_reply() -> None:
    store = InMemorySessionStore()
    backend = RecordingBackend(("a", "b", "c"))
    engine = TurnEngine(store, backend, TickingClock(), turn_id_factory=lambda: "t-1")
    events = engine.handle_turn("s", "hi")
    assert await anext(events) == TextDelta("a")
    await events.aclose()
    assert backend.closed is True  # the abandoned backend stream was closed too
    history = list(await store.history("s"))
    assert [(m.role, m.text) for m in history] == [(Role.USER, "hi")]


async def test_backend_failure_surfaces_typed_after_user_was_persisted() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, MidStreamFailingBackend(), TickingClock())
    events = engine.handle_turn("s", "hi")
    assert await anext(events) == TextDelta("partial ")
    with pytest.raises(InferenceError, match="mid-stream"):
        await anext(events)
    history = list(await store.history("s"))
    assert [(m.role, m.text) for m in history] == [(Role.USER, "hi")]


async def test_plain_async_iterator_backend_completes_normally() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(
        store, PlainIteratorBackend(("x", "y", "z")), TickingClock(), turn_id_factory=lambda: "t-1"
    )
    events = await _collect(engine.handle_turn("s", "hi"))
    assert events[-1] == TurnCompleted(turn_id="t-1", full_text="xyz")
    assert [m.text for m in await store.history("s")] == ["hi", "xyz"]
