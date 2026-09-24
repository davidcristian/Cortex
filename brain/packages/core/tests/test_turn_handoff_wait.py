import asyncio
from datetime import UTC, datetime

import pytest

from cortex_core import (
    HANDOFF_AHEAD_DETAIL,
    SWAPPING,
    EchoInferenceBackend,
    InMemorySessionStore,
    Message,
    RecordingProgressSink,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyQueue,
    Role,
    ScriptedModelHost,
    StatusUpdate,
    SwappingModelManager,
    TextDelta,
    TurnCapabilities,
    TurnEngine,
    TurnEvent,
    Wait,
)

_HANDOFF_AHEAD = Wait(SWAPPING, HANDOFF_AHEAD_DETAIL)


class _FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 24, 4, 0, tzinfo=UTC)


def _manager() -> SwappingModelManager:
    return SwappingModelManager(
        ScriptedModelHost(running=["cortex"]),
        {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"},
        ResidencyPlan(cortex_model="cortex", brain_model="brain", load_timeout_s=60.0),
        _FixedClock(),
        RecordingSleeper(),
    )


class _HandoffAhead:
    """Another turn's handoff, holding the deep model's scope until the test ends it."""

    def __init__(self, manager: SwappingModelManager) -> None:
        self._manager = manager
        self.entered = asyncio.Event()
        self.leave = asyncio.Event()
        self.task: asyncio.Task[None] = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async with self._manager.swap_scope("brain"):
            self.entered.set()
            await self.leave.wait()

    async def start(self) -> None:
        async with asyncio.timeout(5.0):
            await self.entered.wait()

    async def finish(self) -> None:
        self.leave.set()
        await self.task


async def _settle(turns: int = 10) -> None:
    for _ in range(turns):
        await asyncio.sleep(0)


def _engine(
    store: InMemorySessionStore, progress: RecordingProgressSink, queue: ResidencyQueue | None
) -> TurnEngine:
    return TurnEngine(
        store,
        EchoInferenceBackend(),
        _FixedClock(),
        capabilities=TurnCapabilities(progress=progress, residency=queue),
    )


async def _run(engine: TurnEngine, text: str) -> list[TurnEvent]:
    return [event async for event in engine.handle_turn("s", text, turn_id="t2")]


def _text(events: list[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_a_turn_behind_another_handoff_announces_the_wait_before_its_model_call() -> None:
    manager = _manager()
    handoff = _HandoffAhead(manager)
    await handoff.start()
    store = InMemorySessionStore()
    progress = RecordingProgressSink()
    turn = asyncio.create_task(_run(_engine(store, progress, manager), "hello"))
    await _settle()

    assert not turn.done()
    assert progress.events == (StatusUpdate(state=SWAPPING, detail=HANDOFF_AHEAD_DETAIL),)
    assert progress.waits.current() == _HANDOFF_AHEAD
    assert [message.text for message in await store.history("s")] == ["hello"]

    await handoff.finish()
    async with asyncio.timeout(5.0):
        events = await turn
    assert _text(events) == "reply 1: hello"
    assert progress.waits.current() is None
    assert progress.held.count(_HANDOFF_AHEAD) == 1


async def test_a_turn_reads_its_history_only_once_the_handoff_ahead_of_it_ends() -> None:
    manager = _manager()
    handoff = _HandoffAhead(manager)
    await handoff.start()
    store = InMemorySessionStore()
    turn = asyncio.create_task(_run(_engine(store, RecordingProgressSink(), manager), "hello"))
    await _settle()
    await store.append(
        "s", Message(role=Role.USER, text="later", at=_FixedClock().now(), turn_id="t3")
    )

    await handoff.finish()
    async with asyncio.timeout(5.0):
        events = await turn
    assert _text(events) == "reply 2: later"


async def test_a_turn_with_no_handoff_ahead_announces_no_wait() -> None:
    progress = RecordingProgressSink()
    events = await _run(_engine(InMemorySessionStore(), progress, _manager()), "hello")

    assert _text(events) == "reply 1: hello"
    assert progress.events == ()
    assert _HANDOFF_AHEAD not in progress.held


async def test_a_turn_ended_while_it_waits_closes_its_wait_and_keeps_the_user_message() -> None:
    manager = _manager()
    handoff = _HandoffAhead(manager)
    await handoff.start()
    store = InMemorySessionStore()
    progress = RecordingProgressSink()
    turn = asyncio.create_task(_run(_engine(store, progress, manager), "hello"))
    await _settle()

    turn.cancel()
    with pytest.raises(asyncio.CancelledError):
        await turn
    assert progress.waits.current() is None
    assert [message.text for message in await store.history("s")] == ["hello"]
    assert manager.blocks("cortex")
    await handoff.finish()
    assert not manager.blocks("cortex")
