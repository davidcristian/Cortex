"""Behavior of the converse() stream: mapping, cancel, failure, and teardown paths.

These tests drive the conversation loop directly (no gRPC); the loopback tests in
test_converse_grpc.py prove the same contract over the real wire.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence

from cortex_core import (
    EchoInferenceBackend,
    InferenceError,
    InMemorySessionStore,
    Message,
    Role,
    SessionStoreError,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import (
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    converse,
)
from cortex_seam import Cancel, ClientEvent, ServerEvent, UserTurn


def _user_turn(session_id: str, text: str) -> ClientEvent:
    return ClientEvent(session_id=session_id, user_turn=UserTurn(text=text))


def _cancel(session_id: str) -> ClientEvent:
    return ClientEvent(session_id=session_id, cancel=Cancel())


async def _events_from(*events: ClientEvent) -> AsyncIterator[ClientEvent]:
    for event in events:
        yield event


async def _collect(stream: AsyncIterator[ServerEvent]) -> list[ServerEvent]:
    return [event async for event in stream]


def _delta_texts(events: Sequence[ServerEvent]) -> list[str]:
    return [e.text_delta.text for e in events if e.WhichOneof("event") == "text_delta"]


def _engine(store: InMemorySessionStore | None = None) -> TurnEngine:
    ids = iter(f"t-{n}" for n in range(1, 10))
    return TurnEngine(
        store if store is not None else InMemorySessionStore(),
        EchoInferenceBackend(),
        SystemClock(),
        turn_id_factory=lambda: next(ids),
    )


class CountingFailingStore:
    """SessionStore whose append always raises; records how often it was asked."""

    def __init__(self) -> None:
        self.append_calls = 0

    async def append(self, session_id: str, message: Message) -> None:
        del session_id, message
        self.append_calls += 1
        msg = "redis is down"
        raise SessionStoreError(msg)

    async def history(self, session_id: str) -> Sequence[Message]:
        del session_id
        return ()


class MidStreamFailingBackend:
    """Backend that yields one delta and then fails with the typed error."""

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        yield "partial "
        msg = "backend exploded mid-stream"
        raise InferenceError(msg)


class BrokenBackend:
    """Backend that fails with an unexpected (untyped) error. This is the internal path."""

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        msg = "a bug, not a typed seam failure"
        raise RuntimeError(msg)
        yield ""  # makes this an async generator; never reached


class GatedBackend:
    """First delta immediately, then blocks until cancelled; records calls and closure."""

    def __init__(self) -> None:
        self.calls = 0
        self.closed = asyncio.Event()

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        self.calls += 1
        try:
            yield "never-finished"
            await asyncio.sleep(3600)
        finally:
            self.closed.set()


class TeardownGatedBackend:
    """Blocks mid-stream AND holds its own teardown open until `release` is set."""

    def __init__(self) -> None:
        self.teardown_started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        del model, messages
        try:
            yield "never-finished"
            await asyncio.sleep(3600)
        finally:
            self.teardown_started.set()
            await self.release.wait()


class ExplodingClientEvents:
    """A client stream that fails mid-read (e.g. transport breakage)."""

    def __aiter__(self) -> "ExplodingClientEvents":
        return self

    async def __anext__(self) -> ClientEvent:
        msg = "transport blew up"
        raise RuntimeError(msg)


class ScriptedClientEvents:
    """A client stream the test feeds event by event; `close()` ends the input."""

    def __init__(self) -> None:
        self._events: asyncio.Queue[ClientEvent | None] = asyncio.Queue()

    def send(self, event: ClientEvent) -> None:
        self._events.put_nowait(event)

    def close(self) -> None:
        self._events.put_nowait(None)

    def __aiter__(self) -> "ScriptedClientEvents":
        return self

    async def __anext__(self) -> ClientEvent:
        event = await self._events.get()
        if event is None:
            raise StopAsyncIteration
        return event


class SignalingClientEvents:
    """A client stream that signals once the server has drained it completely."""

    def __init__(self, *events: ClientEvent) -> None:
        self._events = list(events)
        self.drained = asyncio.Event()

    def __aiter__(self) -> "SignalingClientEvents":
        return self

    async def __anext__(self) -> ClientEvent:
        if not self._events:
            self.drained.set()
            raise StopAsyncIteration
        return self._events.pop(0)


async def test_turn_maps_deltas_then_turn_complete() -> None:
    events = await _collect(converse(_engine(), _events_from(_user_turn("s", "hello"))))
    kinds = [e.WhichOneof("event") for e in events]
    assert kinds == ["text_delta", "text_delta", "text_delta", "turn_complete"]
    assert "".join(_delta_texts(events)) == "reply 1: hello"
    assert events[-1].turn_complete.turn_id == "t-1"


async def test_second_turn_on_the_same_stream_keeps_counting() -> None:
    client = _events_from(_user_turn("s", "one"), _user_turn("s", "two"))
    events = await _collect(converse(_engine(), client))
    completions = [e for e in events if e.WhichOneof("event") == "turn_complete"]
    assert [c.turn_complete.turn_id for c in completions] == ["t-1", "t-2"]
    assert "".join(_delta_texts(events[4:])) == "reply 2: two"


async def test_empty_client_stream_yields_nothing() -> None:
    assert await _collect(converse(_engine(), _events_from())) == []


async def test_event_without_payload_is_ignored() -> None:
    client = _events_from(ClientEvent(session_id="s"), _user_turn("s", "hi"))
    events = await _collect(converse(_engine(), client))
    assert "".join(_delta_texts(events)) == "reply 1: hi"


async def test_cancel_without_a_turn_in_flight_is_a_no_op() -> None:
    client = _events_from(_cancel("s"), _user_turn("s", "hi"))
    events = await _collect(converse(_engine(), client))
    assert "".join(_delta_texts(events)) == "reply 1: hi"


async def test_store_failure_becomes_terminal_session_store_seam_error() -> None:
    store = CountingFailingStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    events = await _collect(converse(engine, _events_from(_user_turn("s", "hi"))))
    (only,) = events
    assert only.WhichOneof("event") == "error"
    assert only.error.code == ERROR_CODE_SESSION_STORE_UNAVAILABLE
    assert "redis is down" in only.error.message


async def test_after_a_seam_error_later_user_turns_are_not_started() -> None:
    store = CountingFailingStore()
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    client = SignalingClientEvents(_user_turn("s", "one"), _user_turn("s", "two"))
    stream = converse(engine, client)
    first = await anext(stream)
    assert first.WhichOneof("event") == "error"
    # Hold the stream open until the server has read PAST the second user turn …
    await asyncio.wait_for(client.drained.wait(), timeout=5)
    # … which it must have refused to act on: the stream ends, the store was hit once.
    assert await _collect(stream) == []
    assert store.append_calls == 1


async def test_inference_failure_becomes_inference_failed_after_partial_delta() -> None:
    store = InMemorySessionStore()
    engine = TurnEngine(store, MidStreamFailingBackend(), SystemClock())
    events = await _collect(converse(engine, _events_from(_user_turn("s", "hi"))))
    assert [e.WhichOneof("event") for e in events] == ["text_delta", "error"]
    assert events[-1].error.code == ERROR_CODE_INFERENCE_FAILED
    assert "mid-stream" in events[-1].error.message
    # The user message survived; the partial reply was never persisted.
    assert [(m.role, m.text) for m in await store.history("s")] == [(Role.USER, "hi")]


async def test_unexpected_failure_becomes_internal_seam_error() -> None:
    engine = TurnEngine(InMemorySessionStore(), BrokenBackend(), SystemClock())
    events = await _collect(converse(engine, _events_from(_user_turn("s", "hi"))))
    (only,) = events
    assert only.error.code == ERROR_CODE_INTERNAL
    assert "a bug" in only.error.message


async def test_failing_client_stream_becomes_internal_seam_error() -> None:
    events = await _collect(converse(_engine(), ExplodingClientEvents()))
    (only,) = events
    assert only.error.code == ERROR_CODE_INTERNAL
    assert "transport blew up" in only.error.message


async def test_closing_the_stream_mid_turn_tears_down_pump_and_turn() -> None:
    """Client disconnect: the in-flight turn dies, user message stays, partial drops."""
    store = InMemorySessionStore()
    backend = GatedBackend()
    engine = TurnEngine(store, backend, SystemClock())
    stream = converse(engine, _events_from(_user_turn("s", "hi")))
    first = await anext(stream)
    assert first.text_delta.text == "never-finished"
    await stream.aclose()
    await asyncio.wait_for(backend.closed.wait(), timeout=5)
    assert [(m.role, m.text) for m in await store.history("s")] == [(Role.USER, "hi")]


async def test_cancel_behind_a_queued_turn_stops_current_and_drops_queued() -> None:
    """[UserTurn A, UserTurn B, Cancel]: A dies mid-stream, B never runs at all.

    Dispatch must not block on the running turn. With the old serialized dispatch
    this interleaving deadlocked until A finished (never, here), and the stale
    Cancel then destroyed B instead. The dictated semantics: Cancel stops the
    current turn AND drops everything queued; a dropped turn leaves no trace.
    """
    store = InMemorySessionStore()
    backend = GatedBackend()
    engine = TurnEngine(store, backend, SystemClock())
    client = ScriptedClientEvents()
    stream = converse(engine, client)
    client.send(_user_turn("s", "first"))
    first = await anext(stream)
    assert first.text_delta.text == "never-finished"  # A is mid-stream …
    client.send(_user_turn("s", "second"))  # … B queues behind it …
    client.send(_cancel("s"))  # … and Cancel must act NOW, not after A
    async with asyncio.timeout(5):
        await backend.closed.wait()  # A was actually cancelled mid-stream
    client.close()
    assert await _collect(stream) == []  # no TurnComplete for A, nothing from B
    assert backend.calls == 1  # B was dropped while queued: it never ran
    # A's user message persisted without a partial reply; B's was never persisted.
    assert [(m.role, m.text) for m in await store.history("s")] == [(Role.USER, "first")]


async def test_closing_the_stream_during_cancel_teardown_does_not_hang() -> None:
    """Stream teardown racing a Cancel-initiated turn teardown must still aclose().

    The old `suppress(CancelledError): await turn` swallowed the PUMP'S own
    cancellation here: the pump resumed reading the client iterator and aclose()
    hung forever, pinning the RPC handler.
    """
    store = InMemorySessionStore()
    backend = TeardownGatedBackend()
    engine = TurnEngine(store, backend, SystemClock())
    client = ScriptedClientEvents()
    stream = converse(engine, client)
    client.send(_user_turn("s", "hi"))
    first = await anext(stream)
    assert first.text_delta.text == "never-finished"
    client.send(_cancel("s"))  # the pump cancels the turn and waits on its teardown …
    async with asyncio.timeout(5):
        await backend.teardown_started.wait()  # … which is now gated in flight …
    # … and the consumer closes the stream mid-race. aclose() must complete on its
    # own (teardown re-cancels the gated turn; `release` is never set). The shield
    # keeps the timeout from cancelling aclose itself, so a regression fails loudly.
    closer = asyncio.create_task(stream.aclose())
    async with asyncio.timeout(5):
        await asyncio.shield(closer)
    assert [(m.role, m.text) for m in await store.history("s")] == [(Role.USER, "hi")]
