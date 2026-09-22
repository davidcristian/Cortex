import asyncio
from collections.abc import AsyncGenerator, AsyncIterator

from cortex_core import TextDelta, TurnCompleted, TurnEvent
from cortex_orchestrator import converse
from cortex_orchestrator.converse_stream import HEARTBEAT_PERIOD_MS
from cortex_seam import ClientEvent, ServerEvent, UserTurn


class _StepSleeper:
    """Sleeper whose every wait lasts until the test calls ``tick``."""

    def __init__(self) -> None:
        self.waits: list[float] = []
        self._permits: asyncio.Queue[None] = asyncio.Queue()
        self._started = asyncio.Condition()

    async def sleep(self, seconds: float) -> None:
        """Record the wait, then hold until one tick is granted."""
        self.waits.append(seconds)
        async with self._started:
            self._started.notify_all()
        await self._permits.get()

    def tick(self) -> None:
        """End one wait, now or whenever the next one starts."""
        self._permits.put_nowait(None)

    async def waited(self, count: int) -> None:
        """Return once ``count`` waits have started."""
        async with self._started:
            await self._started.wait_for(lambda: len(self.waits) >= count)


class _HeldTurn:
    """TurnRunner that streams two deltas, then holds until released, then completes."""

    def __init__(self) -> None:
        self.said_both = asyncio.Event()
        self.release = asyncio.Event()

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Stream two deltas, wait for the release, then finish."""
        del session_id, text
        yield TextDelta("one")
        yield TextDelta("two")
        self.said_both.set()
        await self.release.wait()
        yield TurnCompleted(turn_id=turn_id, full_text="onetwo")


class _SteppedTurn:
    """TurnRunner that streams one delta, holds, streams two more, holds again, then completes."""

    def __init__(self) -> None:
        self.go = asyncio.Event()
        self.said_three = asyncio.Event()
        self.finish = asyncio.Event()

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str
    ) -> AsyncGenerator[TurnEvent, None]:
        """Stream one delta, then two more once released, then finish once released again."""
        del session_id, text
        yield TextDelta("one")
        await self.go.wait()
        yield TextDelta("two")
        yield TextDelta("three")
        self.said_three.set()
        await self.finish.wait()
        yield TurnCompleted(turn_id=turn_id, full_text="onetwothree")


_LIMIT_S = 5.0


async def _one_turn() -> AsyncIterator[ClientEvent]:
    yield ClientEvent(session_id="s", user_turn=UserTurn(text="hi"))


def _kind(event: ServerEvent) -> str | None:
    return event.WhichOneof("event")


async def test_a_held_turn_is_sent_a_heartbeat_each_period_and_nothing_else() -> None:
    async with asyncio.timeout(_LIMIT_S):
        sleeper = _StepSleeper()
        turn = _HeldTurn()
        stream = converse(lambda _c, _p: turn, _one_turn(), sleeper=sleeper)
        assert _kind(await anext(stream)) == "text_delta"
        assert _kind(await anext(stream)) == "text_delta"
        await turn.said_both.wait()
        sleeper.tick()
        assert _kind(await anext(stream)) == "heartbeat"
        sleeper.tick()
        assert _kind(await anext(stream)) == "heartbeat"
        turn.release.set()
        assert [_kind(event) async for event in stream] == ["turn_complete"]
        assert set(sleeper.waits) == {HEARTBEAT_PERIOD_MS / 1000}


async def test_no_heartbeat_is_queued_behind_an_event_not_yet_sent() -> None:
    async with asyncio.timeout(_LIMIT_S):
        sleeper = _StepSleeper()
        turn = _HeldTurn()
        stream = converse(lambda _c, _p: turn, _one_turn(), sleeper=sleeper)
        assert _kind(await anext(stream)) == "text_delta"
        await turn.said_both.wait()
        sleeper.tick()
        await sleeper.waited(2)
        assert _kind(await anext(stream)) == "text_delta"
        sleeper.tick()
        assert _kind(await anext(stream)) == "heartbeat"
        turn.release.set()
        assert [_kind(event) async for event in stream] == ["turn_complete"]


async def test_no_heartbeat_is_sent_while_no_turn_runs() -> None:
    async with asyncio.timeout(_LIMIT_S):
        sleeper = _StepSleeper()
        input_done = asyncio.Event()

        async def idle_input() -> AsyncIterator[ClientEvent]:
            await input_done.wait()
            for event in list[ClientEvent]():
                yield event

        async def run() -> list[ServerEvent]:
            stream = converse(lambda _c, _p: _HeldTurn(), idle_input(), sleeper=sleeper)
            return [event async for event in stream]

        reader = asyncio.create_task(run())
        await sleeper.waited(1)
        sleeper.tick()
        await sleeper.waited(2)
        input_done.set()
        assert await reader == []


async def test_closing_the_stream_stops_the_heartbeat() -> None:
    async with asyncio.timeout(_LIMIT_S):
        sleeper = _StepSleeper()
        turn = _HeldTurn()
        stream = converse(lambda _c, _p: turn, _one_turn(), sleeper=sleeper)
        assert _kind(await anext(stream)) == "text_delta"
        await stream.aclose()
        waits = len(sleeper.waits)
        sleeper.tick()
        await asyncio.sleep(0)
        assert len(sleeper.waits) == waits


async def test_a_heartbeat_returns_the_buffer_credit_it_takes() -> None:
    async with asyncio.timeout(_LIMIT_S):
        sleeper = _StepSleeper()
        turn = _SteppedTurn()
        stream = converse(lambda _c, _p: turn, _one_turn(), max_buffered_events=1, sleeper=sleeper)
        assert _kind(await anext(stream)) == "text_delta"
        sleeper.tick()
        assert _kind(await anext(stream)) == "heartbeat"
        turn.go.set()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not turn.said_three.is_set()
        assert _kind(await anext(stream)) == "text_delta"
        assert _kind(await anext(stream)) == "text_delta"
        turn.finish.set()
        assert [_kind(event) async for event in stream] == ["turn_complete"]
