import pytest

from cortex_core import (
    ASKING,
    CALLING,
    DELEGATING,
    FOLDING,
    GENERATING,
    QUEUED,
    SWAPPING,
    THINKING,
    TOOL_RUNNING,
    USER_ASKED,
    WAIT_KEYS,
    RecordingProgressSink,
    StatusUpdate,
    TurnWaits,
    Wait,
    hold_wait,
)

_SWAP = Wait(SWAPPING, "loading the deep model")


class _BoomError(Exception):
    pass


def _record() -> tuple[TurnWaits, list[StatusUpdate]]:
    sent: list[StatusUpdate] = []

    async def emit(event: StatusUpdate) -> None:
        sent.append(event)

    return TurnWaits(emit), sent


def test_the_keys_are_the_seven_plain_verbs() -> None:
    assert WAIT_KEYS == (THINKING, QUEUED, DELEGATING, SWAPPING, FOLDING, CALLING, ASKING)
    assert WAIT_KEYS == (
        "thinking",
        "queued",
        "delegating",
        "swapping",
        "folding",
        "calling",
        "asking",
    )


async def test_a_record_with_nothing_open_waits_on_nothing() -> None:
    waits, sent = _record()
    assert waits.current() is None
    async with waits.hold(TOOL_RUNNING):
        pass
    assert waits.current() is None
    assert sent == [StatusUpdate(state=CALLING, detail=TOOL_RUNNING.detail)]


async def test_the_innermost_open_wait_wins_until_it_closes() -> None:
    waits, _ = _record()
    async with waits.hold(TOOL_RUNNING):
        async with waits.hold(USER_ASKED):
            assert waits.current() == USER_ASKED
        assert waits.current() == TOOL_RUNNING


async def test_a_wait_closed_out_of_order_leaves_the_others_in_place() -> None:
    waits, _ = _record()
    outer = waits.hold(TOOL_RUNNING)
    inner = waits.hold(USER_ASKED)
    await outer.__aenter__()
    await inner.__aenter__()
    await outer.__aexit__(None, None, None)
    assert waits.current() == USER_ASKED
    await inner.__aexit__(None, None, None)
    assert waits.current() is None


async def test_a_wait_closes_when_its_block_raises() -> None:
    waits, _ = _record()
    with pytest.raises(_BoomError):
        async with waits.hold(TOOL_RUNNING):
            raise _BoomError
    assert waits.current() is None


async def test_a_change_to_a_wait_other_than_thinking_is_sent_as_a_status() -> None:
    waits, sent = _record()
    async with waits.hold(GENERATING), waits.hold(TOOL_RUNNING), waits.hold(USER_ASKED):
        pass
    assert sent == [
        StatusUpdate(state=CALLING, detail=TOOL_RUNNING.detail),
        StatusUpdate(state=ASKING, detail=USER_ASKED.detail),
        StatusUpdate(state=CALLING, detail=TOOL_RUNNING.detail),
    ]


async def test_a_thinking_wait_is_never_sent_as_a_status() -> None:
    waits, sent = _record()
    async with waits.hold(TOOL_RUNNING), waits.hold(GENERATING):
        assert waits.current() == GENERATING
    assert [event.state for event in sent] == [CALLING, CALLING]


async def test_reopening_the_same_wait_sends_nothing_new() -> None:
    waits, sent = _record()
    async with waits.hold(TOOL_RUNNING), waits.hold(TOOL_RUNNING):
        pass
    assert sent == [StatusUpdate(state=CALLING, detail=TOOL_RUNNING.detail)]


async def test_a_quiet_hold_is_recorded_without_a_status() -> None:
    waits, sent = _record()
    async with waits.hold(_SWAP, announce=False) as held:
        assert waits.current() == _SWAP
        await held.restate(Wait(SWAPPING, "bringing the usual assistant back"), announce=False)
        assert waits.current() == Wait(SWAPPING, "bringing the usual assistant back")
    assert sent == []


async def test_a_restated_wait_is_sent_only_while_it_is_the_innermost() -> None:
    waits, sent = _record()
    async with waits.hold(Wait(QUEUED, "2 subtasks waiting for room to run")) as batch:
        async with waits.hold(USER_ASKED):
            await batch.restate(Wait(DELEGATING, "2 subtasks running"))
            assert waits.current() == USER_ASKED
        await batch.restate(Wait(DELEGATING, "1 subtask running"))
    assert [(event.state, event.detail) for event in sent] == [
        (QUEUED, "2 subtasks waiting for room to run"),
        (ASKING, USER_ASKED.detail),
        (DELEGATING, "2 subtasks running"),
        (DELEGATING, "1 subtask running"),
    ]


async def test_hold_wait_without_a_sink_holds_nothing() -> None:
    async with hold_wait(None, TOOL_RUNNING) as held:
        assert held is None


async def test_hold_wait_holds_on_the_sink_it_is_given() -> None:
    sink = RecordingProgressSink()
    async with hold_wait(sink, TOOL_RUNNING):
        assert sink.waits.current() == TOOL_RUNNING
    assert sink.held == (TOOL_RUNNING,)
    assert sink.events == (StatusUpdate(state=CALLING, detail=TOOL_RUNNING.detail),)
