"""The `ProgressSink` contract, checked against every implementation of the port."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from cortex_core import (
    ASKING,
    CALLING,
    GENERATING,
    SWAPPING,
    TOOL_RUNNING,
    USER_ASKED,
    ProgressSink,
    Wait,
)

_SWAP = Wait(SWAPPING, "loading the deep model")


@dataclass(frozen=True, slots=True)
class SinkUnderTest:
    """One implementation, the statuses it put on the stream, and the wait it reports now."""

    sink: ProgressSink
    sent: Callable[[], Sequence[tuple[str, str]]]
    current: Callable[[], Wait | None]


type Check = Callable[[SinkUnderTest], Awaitable[None]]


async def the_innermost_open_wait_is_the_current_one(under_test: SinkUnderTest) -> None:
    """A wait opened inside another one is what the turn waits on until it closes."""
    async with under_test.sink.hold(TOOL_RUNNING):
        async with under_test.sink.hold(USER_ASKED):
            assert under_test.current() == USER_ASKED
        assert under_test.current() == TOOL_RUNNING
    assert under_test.current() is None


async def each_change_of_wait_is_sent_as_a_status(under_test: SinkUnderTest) -> None:
    """Opening and closing a wait sends the wait the turn is left on."""
    async with under_test.sink.hold(TOOL_RUNNING), under_test.sink.hold(USER_ASKED):
        pass
    assert list(under_test.sent()) == [
        (CALLING, TOOL_RUNNING.detail),
        (ASKING, USER_ASKED.detail),
        (CALLING, TOOL_RUNNING.detail),
    ]


async def a_thinking_wait_is_never_sent_as_a_status(under_test: SinkUnderTest) -> None:
    """A thinking status holds reasoning text, so the thinking wait goes out only by heartbeat."""
    async with under_test.sink.hold(GENERATING):
        assert under_test.current() == GENERATING
    assert list(under_test.sent()) == []


async def a_quiet_hold_sends_nothing(under_test: SinkUnderTest) -> None:
    """A holder that reports its own wait on the stream opens it without a second status."""
    async with under_test.sink.hold(_SWAP, announce=False):
        assert under_test.current() == _SWAP
    assert list(under_test.sent()) == []


ALL_CHECKS: Sequence[Check] = (
    the_innermost_open_wait_is_the_current_one,
    each_change_of_wait_is_sent_as_a_status,
    a_thinking_wait_is_never_sent_as_a_status,
    a_quiet_hold_sends_nothing,
)
