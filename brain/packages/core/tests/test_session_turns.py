import asyncio
from collections.abc import AsyncIterator, Sequence

from cortex_core import (
    CHAT_AHEAD,
    QUEUED,
    EchoInferenceBackend,
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    RecordingProgressSink,
    Role,
    SerialTurnRunner,
    SessionTurnLocks,
    StatusUpdate,
    SystemClock,
    ToolSpec,
    TurnEngine,
    TurnEvent,
)


class HeldBackend:
    """The echo backend, whose every completion waits until the test releases it."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.started = 0

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        self.started += 1
        await self.release.wait()
        async for event in EchoInferenceBackend().stream(
            model, messages, tools=tools, schema=schema, bounds=bounds
        ):
            yield event


def _runner(
    store: InMemorySessionStore,
    backend: HeldBackend,
    locks: SessionTurnLocks,
    progress: RecordingProgressSink | None = None,
) -> SerialTurnRunner:
    return SerialTurnRunner(TurnEngine(store, backend, SystemClock()), locks, progress)


async def _drain(runner: SerialTurnRunner, session_id: str, text: str) -> list[TurnEvent]:
    events = runner.handle_turn(session_id, text, turn_id=f"turn-{text}")
    try:
        return [event async for event in events]
    finally:
        await events.aclose()


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def _transcript(history: Sequence[Message]) -> list[tuple[Role, str]]:
    return [(message.role, message.text) for message in history]


async def test_a_turn_on_a_busy_session_waits_and_stores_after_the_reply_ahead() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    first = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "first"))
    await _settle()
    second = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "second"))
    await _settle()

    assert backend.started == 1
    assert _transcript(await store.history("s")) == [(Role.USER, "first")]
    backend.release.set()
    await asyncio.gather(first, second)

    assert _transcript(await store.history("s")) == [
        (Role.USER, "first"),
        (Role.ASSISTANT, "reply 1: first"),
        (Role.USER, "second"),
        (Role.ASSISTANT, "reply 2: second"),
    ]
    assert len(locks) == 0


async def test_turns_on_different_sessions_run_together() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    one = asyncio.create_task(_drain(_runner(store, backend, locks), "a", "first"))
    two = asyncio.create_task(_drain(_runner(store, backend, locks), "b", "second"))
    await _settle()

    assert backend.started == 2
    assert len(locks) == 2
    backend.release.set()
    await asyncio.gather(one, two)
    assert len(locks) == 0


async def test_a_waiting_turn_whose_stream_drops_stores_nothing_and_frees_its_place() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    first = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "first"))
    await _settle()
    dropped = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "dropped"))
    third = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "third"))
    await _settle()
    dropped.cancel()
    await asyncio.wait([dropped])
    backend.release.set()
    await asyncio.gather(first, third)

    assert _transcript(await store.history("s")) == [
        (Role.USER, "first"),
        (Role.ASSISTANT, "reply 1: first"),
        (Role.USER, "third"),
        (Role.ASSISTANT, "reply 2: third"),
    ]
    assert len(locks) == 0


async def test_a_turn_cancelled_mid_reply_lets_the_next_one_start() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    stopped = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "stopped"))
    await _settle()
    nxt = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "next"))
    await _settle()
    stopped.cancel()
    await asyncio.wait([stopped])
    await _settle()

    assert backend.started == 2
    backend.release.set()
    await nxt
    assert _transcript(await store.history("s")) == [
        (Role.USER, "stopped"),
        (Role.USER, "next"),
        (Role.ASSISTANT, "reply 2: next"),
    ]
    assert len(locks) == 0


async def test_a_turn_behind_its_own_chat_says_so_until_it_holds_the_chat() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    ahead = RecordingProgressSink()
    behind = RecordingProgressSink()
    first = asyncio.create_task(_drain(_runner(store, backend, locks, ahead), "s", "first"))
    await _settle()
    second = asyncio.create_task(_drain(_runner(store, backend, locks, behind), "s", "second"))
    await _settle()

    assert behind.waits.current() == CHAT_AHEAD
    assert behind.events == (StatusUpdate(state=QUEUED, detail=CHAT_AHEAD.detail),)
    assert ahead.held == ()
    backend.release.set()
    await asyncio.gather(first, second)
    assert behind.waits.current() is None
    assert behind.held == (CHAT_AHEAD,)
    assert ahead.events == ()


async def test_a_turn_on_another_chat_or_a_free_one_holds_no_wait() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    sinks = (RecordingProgressSink(), RecordingProgressSink())
    one = asyncio.create_task(_drain(_runner(store, backend, locks, sinks[0]), "a", "first"))
    two = asyncio.create_task(_drain(_runner(store, backend, locks, sinks[1]), "b", "second"))
    await _settle()
    backend.release.set()
    await asyncio.gather(one, two)
    later = RecordingProgressSink()
    await _drain(_runner(store, backend, locks, later), "a", "third")

    assert [sink.held for sink in (*sinks, later)] == [(), (), ()]


async def test_a_turn_cancelled_while_it_says_it_waits_closes_the_wait() -> None:
    store = InMemorySessionStore()
    backend = HeldBackend()
    locks = SessionTurnLocks()
    behind = RecordingProgressSink()
    first = asyncio.create_task(_drain(_runner(store, backend, locks), "s", "first"))
    await _settle()
    dropped = asyncio.create_task(_drain(_runner(store, backend, locks, behind), "s", "dropped"))
    await _settle()
    dropped.cancel()
    await asyncio.wait([dropped])

    assert behind.waits.current() is None
    backend.release.set()
    await first
    assert len(locks) == 0
