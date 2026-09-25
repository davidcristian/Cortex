import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import cast

import pytest

from cortex_core import (
    HANDOFF_AHEAD_DETAIL,
    SWAPPING,
    TOOL_RUNNING,
    EchoInferenceBackend,
    GenerationBounds,
    HandoffAheadBackend,
    ImagePart,
    InferenceEvent,
    InMemorySessionStore,
    JsonSchema,
    Message,
    ProgressEvent,
    RecordingProgressSink,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyQueue,
    Role,
    ScriptedInferenceBackend,
    ScriptedModelHost,
    ScriptedVisionProbe,
    StatusUpdate,
    SwappingModelManager,
    TextChunk,
    TextDelta,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    TurnEvent,
    Wait,
    wait_out_handoff,
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


class _HandoffAtHistory(InMemorySessionStore):
    """A store whose first history read starts another turn's handoff, after the turn's check."""

    def __init__(self, manager: SwappingModelManager) -> None:
        super().__init__()
        self._manager = manager
        self.handoff: _HandoffAhead | None = None

    async def history(self, session_id: str) -> Sequence[Message]:
        if self.handoff is None:
            self.handoff = _HandoffAhead(self._manager)
            await self.handoff.start()
        return await super().history(session_id)


async def test_a_handoff_that_begins_after_the_turn_s_check_is_announced_at_its_model_call() -> (
    None
):
    manager = _manager()
    store = _HandoffAtHistory(manager)
    progress = RecordingProgressSink()
    model = ScriptedInferenceBackend([[TextChunk("hi")]])
    engine = TurnEngine(
        store,
        HandoffAheadBackend(model, manager, progress),
        _FixedClock(),
        capabilities=TurnCapabilities(progress=progress, residency=manager),
    )
    turn = asyncio.create_task(_run(engine, "hello"))
    await _settle()

    assert store.handoff is not None
    assert not turn.done()
    assert model.calls == []
    assert progress.events == (StatusUpdate(state=SWAPPING, detail=HANDOFF_AHEAD_DETAIL),)
    assert progress.waits.current() == _HANDOFF_AHEAD

    await store.handoff.finish()
    async with asyncio.timeout(5.0):
        events = await turn
    assert _text(events) == "hi"
    assert model.calls == ["cortex"]
    assert progress.waits.current() is None


def _hello() -> list[Message]:
    return [Message(role=Role.USER, text="hello", at=_FixedClock().now(), turn_id="t2")]


async def test_a_model_call_with_no_handoff_ahead_streams_at_once_and_holds_no_wait() -> None:
    progress = RecordingProgressSink()
    backend = HandoffAheadBackend(
        ScriptedInferenceBackend([[TextChunk("hi")]]), _manager(), progress
    )

    events = [event async for event in backend.stream("cortex", _hello())]

    assert events == [TextChunk("hi")]
    assert progress.held == ()


class _SecondHandoffSink(RecordingProgressSink):
    """Starts a second handoff as the first wait closes and the outer wait is announced again."""

    def __init__(self, manager: SwappingModelManager) -> None:
        super().__init__()
        self._manager = manager
        self.second: _HandoffAhead | None = None

    async def emit(self, event: ProgressEvent) -> None:
        await super().emit(event)
        restated = self.events.count(
            StatusUpdate(state=TOOL_RUNNING.key, detail=TOOL_RUNNING.detail)
        )
        if restated == 2 and self.second is None:
            self.second = _HandoffAhead(self._manager)
            await self.second.start()


async def test_a_handoff_that_begins_as_the_wait_closes_is_waited_out_too() -> None:
    manager = _manager()
    first = _HandoffAhead(manager)
    await first.start()
    sink = _SecondHandoffSink(manager)

    async def waited() -> None:
        async with sink.hold(TOOL_RUNNING):
            await wait_out_handoff(manager, sink, "cortex")

    task = asyncio.create_task(waited())
    await _settle()
    await first.finish()
    await _settle()

    assert sink.second is not None
    assert not task.done()
    assert sink.held.count(_HANDOFF_AHEAD) == 2
    assert sink.waits.current() == _HANDOFF_AHEAD
    await sink.second.finish()
    async with asyncio.timeout(5.0):
        await task


class _Tracked:
    def __init__(self) -> None:
        self.closed = False

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
        try:
            yield TextChunk("a")
            yield TextChunk("b")
        finally:
            self.closed = True


async def test_closing_a_model_call_early_closes_the_wrapped_stream() -> None:
    inner = _Tracked()
    events = cast(
        "AsyncGenerator[InferenceEvent, None]",
        HandoffAheadBackend(inner, _manager(), None).stream("cortex", _hello()),
    )

    assert await anext(events) == TextChunk("a")
    await events.aclose()

    assert inner.closed


class _Plain:
    """A backend whose stream is an iterator object, not a generator, so it has no ``aclose``."""

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
        return _Once(TextChunk("only"))


class _Once:
    def __init__(self, event: InferenceEvent) -> None:
        self._left = [event]

    def __aiter__(self) -> "_Once":
        return self

    async def __anext__(self) -> InferenceEvent:
        if not self._left:
            raise StopAsyncIteration
        return self._left.pop()


async def test_a_wrapped_stream_that_is_not_a_generator_streams_to_its_end() -> None:
    backend = HandoffAheadBackend(_Plain(), _manager(), None)

    assert [event async for event in backend.stream("cortex", _hello())] == [TextChunk("only")]


async def test_a_turn_with_a_picture_asks_whether_the_model_sees_only_after_the_handoff() -> None:
    manager = _manager()
    handoff = _HandoffAhead(manager)
    await handoff.start()
    store = InMemorySessionStore()
    probe = ScriptedVisionProbe([True])
    engine = TurnEngine(
        store,
        EchoInferenceBackend(),
        _FixedClock(),
        capabilities=TurnCapabilities(residency=manager, sight=probe),
    )
    picture = ImagePart(
        data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, mime_type="image/png", width=64, height=48
    )

    async def attached() -> list[TurnEvent]:
        return [e async for e in engine.handle_turn("s", "hi", turn_id="t2", images=(picture,))]

    turn = asyncio.create_task(attached())
    await _settle()

    assert not turn.done()
    assert probe.asked == 0
    assert await store.history("s") == ()

    await handoff.finish()
    async with asyncio.timeout(5.0):
        await turn
    assert probe.asked == 1
