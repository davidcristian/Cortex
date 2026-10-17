import asyncio
import contextlib
from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from cortex_core import (
    LOAD_POLL_INTERVAL_S,
    MODEL_LOADING,
    ImagePart,
    InferenceError,
    InferenceEvent,
    Message,
    ModelLoadingError,
    RecordingProgressSink,
    RecordingSleeper,
    StatusUpdate,
    TextChunk,
    TurnCompleted,
    TurnEvent,
)
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.load_wait import LoadWaitBackend, LoadWaitTurns
from cortex_core.tools import ToolSpec

_START = datetime(2026, 10, 16, 6, 0, tzinfo=UTC)
_LOADING = ModelLoadingError("model 'cortex' is still loading")

type Answer = InferenceError | Sequence[InferenceEvent]


class _SteppingClock:
    def __init__(self) -> None:
        self.readings = 0

    def now(self) -> datetime:
        at = _START + timedelta(seconds=self.readings)
        self.readings += 1
        return at


class _AnsweringBackend:
    def __init__(self, answers: Sequence[Answer], *, fail_after_first: bool = False) -> None:
        self._answers = list(answers)
        self._fail_after_first = fail_after_first
        self.calls = 0
        self.closed = 0

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
        answer = self._answers[min(self.calls, len(self._answers) - 1)]
        self.calls += 1
        try:
            if isinstance(answer, InferenceError):
                raise answer
            for event in answer:
                yield event
                if self._fail_after_first:
                    raise _LOADING
        finally:
            self.closed += 1


class _BlockingSleeper:
    def __init__(self) -> None:
        self.entered = asyncio.Event()

    async def sleep(self, seconds: float) -> None:
        del seconds
        self.entered.set()
        await asyncio.Event().wait()


def _waiting(
    inner: _AnsweringBackend,
    progress: RecordingProgressSink | None,
    *,
    wait_s: float,
    sleeper: RecordingSleeper | _BlockingSleeper | None = None,
) -> LoadWaitBackend:
    return LoadWaitBackend(
        inner,
        progress,
        clock=_SteppingClock(),
        sleeper=RecordingSleeper() if sleeper is None else sleeper,
        wait_s=wait_s,
    )


async def _drain(backend: LoadWaitBackend) -> list[InferenceEvent]:
    return [event async for event in backend.stream("cortex", [])]


async def test_a_loading_server_is_asked_again_until_it_answers() -> None:
    inner = _AnsweringBackend([_LOADING, _LOADING, [TextChunk("Rhine"), TextChunk(".")]])
    progress = RecordingProgressSink()
    sleeper = RecordingSleeper()

    events = await _drain(_waiting(inner, progress, wait_s=60.0, sleeper=sleeper))

    assert events == [TextChunk("Rhine"), TextChunk(".")]
    assert inner.calls == 3
    assert inner.closed == 3
    assert sleeper.waits == [LOAD_POLL_INTERVAL_S, LOAD_POLL_INTERVAL_S]
    assert progress.held == (MODEL_LOADING,)
    assert progress.events == (
        StatusUpdate(state=MODEL_LOADING.key, detail=MODEL_LOADING.detail),
        StatusUpdate(state="", detail=""),
    )
    assert progress.waits.current() is None


async def test_the_wait_ends_before_the_first_event_is_passed_on() -> None:
    inner = _AnsweringBackend([_LOADING, [TextChunk("Rhine")]])
    progress = RecordingProgressSink()
    seen = [
        progress.waits.current()
        async for _ in _waiting(inner, progress, wait_s=60.0).stream("cortex", [])
    ]

    assert seen == [None]


async def test_a_server_still_loading_at_the_bound_ends_the_turn_with_the_loading_error() -> None:
    inner = _AnsweringBackend([_LOADING])
    progress = RecordingProgressSink()
    sleeper = RecordingSleeper()

    with pytest.raises(ModelLoadingError) as raised:
        await _drain(_waiting(inner, progress, wait_s=2.0, sleeper=sleeper))

    assert raised.value is _LOADING
    assert inner.calls == 3
    assert sleeper.waits == [LOAD_POLL_INTERVAL_S, LOAD_POLL_INTERVAL_S]
    assert progress.waits.current() is None


async def test_a_zero_bound_ends_the_turn_at_once() -> None:
    inner = _AnsweringBackend([_LOADING])
    progress = RecordingProgressSink()
    sleeper = RecordingSleeper()

    with pytest.raises(ModelLoadingError):
        await _drain(_waiting(inner, progress, wait_s=0.0, sleeper=sleeper))

    assert inner.calls == 1
    assert sleeper.waits == []
    assert progress.held == ()


async def test_any_other_failure_ends_the_turn_at_once() -> None:
    down = InferenceError("llama-server request failed for model 'cortex'")
    inner = _AnsweringBackend([down])
    progress = RecordingProgressSink()
    sleeper = RecordingSleeper()

    with pytest.raises(InferenceError) as raised:
        await _drain(_waiting(inner, progress, wait_s=60.0, sleeper=sleeper))

    assert raised.value is down
    assert inner.calls == 1
    assert sleeper.waits == []
    assert progress.held == ()


async def test_a_loading_answer_after_the_first_event_is_not_asked_again() -> None:
    inner = _AnsweringBackend([[TextChunk("Rhine")]], fail_after_first=True)
    stream = _waiting(inner, RecordingProgressSink(), wait_s=60.0).stream("cortex", [])

    assert await anext(stream) == TextChunk("Rhine")
    with pytest.raises(ModelLoadingError):
        await anext(stream)
    assert inner.calls == 1


async def test_stop_during_the_wait_cancels_it_and_releases_the_status() -> None:
    inner = _AnsweringBackend([_LOADING])
    progress = RecordingProgressSink()
    sleeper = _BlockingSleeper()
    turn = asyncio.create_task(_drain(_waiting(inner, progress, wait_s=60.0, sleeper=sleeper)))
    await sleeper.entered.wait()

    turn.cancel()

    with pytest.raises(asyncio.CancelledError):
        await turn
    assert progress.held == (MODEL_LOADING,)
    assert progress.waits.current() is None
    assert inner.calls == 1


async def test_a_turn_with_no_progress_sink_still_waits() -> None:
    inner = _AnsweringBackend([_LOADING, [TextChunk("Rhine")]])

    events = await _drain(_waiting(inner, None, wait_s=60.0))

    assert events == [TextChunk("Rhine")]
    assert inner.calls == 2


class _Once:
    def __init__(self, answer: Answer) -> None:
        self._answer = answer
        self._left = True

    def __aiter__(self) -> "_Once":
        return self

    async def __anext__(self) -> InferenceEvent:
        if isinstance(self._answer, InferenceError):
            raise self._answer
        if not self._left:
            raise StopAsyncIteration
        self._left = False
        return self._answer[0]


class _Plain:
    def __init__(self, answers: Sequence[Answer]) -> None:
        self._answers = list(answers)

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
        return _Once(self._answers.pop(0))


async def test_a_wrapped_stream_that_is_not_a_generator_is_asked_again_and_streams() -> None:
    backend = LoadWaitBackend(
        _Plain([_LOADING, [TextChunk("only")]]),
        None,
        clock=_SteppingClock(),
        sleeper=RecordingSleeper(),
        wait_s=60.0,
    )

    assert await _drain(backend) == [TextChunk("only")]


async def test_a_consumer_that_stops_early_closes_the_wrapped_stream() -> None:
    inner = _AnsweringBackend([[TextChunk("Rhine"), TextChunk(".")]])
    stream = cast(
        "AsyncGenerator[InferenceEvent]",
        _waiting(inner, RecordingProgressSink(), wait_s=60.0).stream("cortex", []),
    )

    assert await anext(stream) == TextChunk("Rhine")
    await stream.aclose()

    assert inner.closed == 1


class _Ticking:
    def __init__(self) -> None:
        self.at = _START

    def now(self) -> datetime:
        return self.at

    async def sleep(self, seconds: float) -> None:
        self.at += timedelta(seconds=seconds)

    def elapsed(self) -> float:
        return (self.at - _START).total_seconds()


def _ticking(inner: _AnsweringBackend, clock: _Ticking) -> LoadWaitBackend:
    return LoadWaitBackend(inner, None, clock=clock, sleeper=clock, wait_s=120.0)


async def _gave_up_at(backend: LoadWaitBackend, clock: _Ticking) -> float:
    with pytest.raises(ModelLoadingError):
        await _drain(backend)
    return clock.elapsed()


async def test_the_model_calls_of_one_turn_wait_one_bound_in_all() -> None:
    clock = _Ticking()
    backend = _ticking(_AnsweringBackend([_LOADING]), clock)

    with backend.turn():
        ends = [await _gave_up_at(backend, clock) for _ in ("judge", "recap", "reply")]

    assert ends == [120.0, 120.0, 120.0]


async def test_each_call_outside_a_turn_waits_its_own_bound() -> None:
    clock = _Ticking()
    backend = _ticking(_AnsweringBackend([_LOADING]), clock)

    ends = [await _gave_up_at(backend, clock) for _ in ("judge", "reply")]

    assert ends == [120.0, 240.0]


class _JudgeThenReply:
    def __init__(self, backend: LoadWaitBackend) -> None:
        self._backend = backend
        self.replies: list[list[InferenceEvent]] = []

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent]:
        del session_id, text, turn_id, images
        with contextlib.suppress(InferenceError):
            await _drain(self._backend)
        self.replies.append(await _drain(self._backend))
        return
        yield


async def _run_turn(turns: LoadWaitTurns) -> None:
    async for _ in turns.handle_turn("s", "rivers?", turn_id="t"):
        pass


async def test_every_turn_waits_a_fresh_bound_and_none_is_kept_after_it() -> None:
    clock = _Ticking()
    backend = _ticking(_AnsweringBackend([_LOADING]), clock)
    turns = LoadWaitTurns(_JudgeThenReply(backend), backend)

    ends = [await _gave_up_at_turn(turns, clock) for _ in ("first", "second")]

    assert ends == [120.0, 240.0]
    assert await _gave_up_at(backend, clock) == 360.0


async def _gave_up_at_turn(turns: LoadWaitTurns, clock: _Ticking) -> float:
    with pytest.raises(ModelLoadingError):
        await _run_turn(turns)
    return clock.elapsed()


async def test_a_turn_whose_server_loads_inside_the_bound_still_answers() -> None:
    clock = _Ticking()
    backend = _ticking(_AnsweringBackend([_LOADING, _LOADING, [TextChunk("Rhine")]]), clock)
    runner = _JudgeThenReply(backend)

    await _run_turn(LoadWaitTurns(runner, backend))

    assert runner.replies == [[TextChunk("Rhine")]]
    assert clock.elapsed() == 2 * LOAD_POLL_INTERVAL_S


def test_the_turn_runner_exposes_the_runner_it_wraps() -> None:
    backend = _ticking(_AnsweringBackend([_LOADING]), _Ticking())
    runner = _JudgeThenReply(backend)

    assert LoadWaitTurns(runner, backend).inner is runner


class _TwoEvents:
    def __init__(self) -> None:
        self.closed = False

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent]:
        del session_id, text, images
        try:
            yield TurnCompleted(turn_id=turn_id, full_text="one")
            yield TurnCompleted(turn_id=turn_id, full_text="two")
        finally:
            self.closed = True


async def test_a_turn_consumer_that_stops_early_closes_the_wrapped_turn() -> None:
    runner = _TwoEvents()
    backend = _ticking(_AnsweringBackend([_LOADING]), _Ticking())
    events = LoadWaitTurns(runner, backend).handle_turn("s", "rivers?", turn_id="t")

    assert await anext(events) == TurnCompleted(turn_id="t", full_text="one")
    await events.aclose()

    assert runner.closed
