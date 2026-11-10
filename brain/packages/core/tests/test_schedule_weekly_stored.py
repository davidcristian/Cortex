from collections.abc import Mapping

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    StopLedger,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_daily import DAILY_STORED_NOTE
from cortex_core.schedule_first_fire import FIRST_FIRE_NOTE
from cortex_core.schedule_tools import DAILY_NOTE
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.schedule_weekly_stored import (
    WEEKLY_STORED_NOTE,
    weekly_after,
    weekly_stored_notes,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_CAR = "Remember that I park on level 3 and remind me tomorrow at 9 to move the car."
_WED = {"kind": "reminder", "text": "move the car", "at_time": "09:00", "on_days": ["wed"]}
_STORED = "scheduled reminder abc: due 2026-11-11T09:00:00+01:00 (tomorrow), every wed at 09:00"
_NOTE = (
    "\n\n(A reminder set in this turn repeats every Wednesday. Ask to make it one time if you "
    "meant only once.)"
)
_HELD = (("abc", "Wednesday"),)


def _ran(content: str = _STORED, *, failed: bool = False) -> ToolResult:
    return ToolResult(call_id="c", content=content, trust=Trust.TRUSTED, is_error=failed)


def _call(arguments: Mapping[str, object] = _WED, name: str = SCHEDULE_TOOL_NAME) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


@pytest.mark.parametrize(
    "reply",
    [
        "I'll remind you every Wednesday at 9:00 to move the car.",
        "Done. I'll remind you on Wednesdays at 9:00.",
        "Your reminder goes off each week on Wednesday at 9:00.",
        "I've set a weekly reminder for Wednesday at 9:00.",
        "This reminder repeats on Wednesday at 9:00.",
    ],
)
def test_a_reply_stating_the_repeat_has_no_note(reply: str) -> None:
    assert weekly_stored_notes(_HELD, reply) == ()


@pytest.mark.parametrize(
    "reply",
    [
        "I'll remind you tomorrow at 9:00 AM to move the car.",
        "I'll remind you on Wednesday at 9:00.",
        "Reminder set for tomorrow at 9:00 to send the weekly report.",
        "Should it repeat every Wednesday?",
        "It will not repeat every Wednesday.",
        "Let me know if you want it every Wednesday.",
    ],
)
def test_a_reply_stating_no_repeat_closes_with_the_note(reply: str) -> None:
    assert weekly_stored_notes(_HELD, reply) == (_NOTE,)


def test_a_rule_on_chosen_days_is_held_with_its_weekdays_in_order() -> None:
    assert weekly_after(_call(), _ran(), ()) == _HELD
    days = {**_WED, "on_days": ["fri", "mon", "wed"]}
    held = weekly_after(_call(days), _ran(), ())
    assert held == (("abc", "Monday, Wednesday and Friday"),)
    assert weekly_stored_notes(held, "Done.") == (
        WEEKLY_STORED_NOTE.format(days="Monday, Wednesday and Friday"),
    )


@pytest.mark.parametrize(
    ("arguments", "content", "failed"),
    [
        (_WED, _STORED, True),
        ({**_WED, "on_days": None}, _STORED, False),
        ({"kind": "reminder", "text": "t", "at": "2026-11-11T09:00:00"}, _STORED, False),
        (
            {**_WED, "on_days": ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]},
            _STORED + DAILY_NOTE,
            False,
        ),
        ({**_WED, "on_days": ["wed"], "at_time": None}, _STORED, False),
        ({**_WED, "on_days": ["midweek"]}, _STORED, False),
        (_WED, "not scheduled", False),
    ],
)
def test_a_store_without_a_rule_on_chosen_days_is_not_held(
    *, arguments: Mapping[str, object], content: str, failed: bool
) -> None:
    assert weekly_after(_call(arguments), _ran(content, failed=failed), ()) == ()


def test_an_edit_with_on_days_is_not_held() -> None:
    edit = _call({"id": "abc", "at_time": "09:00", "on_days": ["wed"]}, EDIT_SCHEDULED_TOOL_NAME)
    assert weekly_after(edit, _ran(), ()) == ()


@pytest.mark.parametrize(
    ("name", "arguments", "kept"),
    [
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "abc"}, False),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "def"}, True),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at": "2026-11-11T09:00:00"}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "every_seconds": 0}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "10:00"}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "on_days": ["thu"]}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "move it"}, True),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "abc", "minutes": 10}, True),
    ],
)
def test_an_end_of_the_rule_drops_it_and_another_change_keeps_it(
    *, name: str, arguments: Mapping[str, object], kept: bool
) -> None:
    after = weekly_after(_call(arguments, name), _ran("done"), _HELD)
    assert after == (_HELD if kept else ())


def test_a_failed_cancel_keeps_the_rule() -> None:
    cancel = _call({"id": "abc"}, CANCEL_SCHEDULED_TOOL_NAME)
    assert weekly_after(cancel, _ran("no such item", failed=True), _HELD) == _HELD


def test_two_rules_on_the_same_days_have_one_note() -> None:
    held = (*_HELD, ("def", "Wednesday"), ("ghi", "Thursday"))
    assert weekly_stored_notes(held, "Done.") == (
        _NOTE,
        WEEKLY_STORED_NOTE.format(days="Thursday"),
    )


def test_a_turn_holding_a_rule_closes_with_its_note_after_the_first_fire_note() -> None:
    parts = ["I'll remind you tomorrow at 9:00 AM to move the car."]
    first = FIRST_FIRE_NOTE.format(when="today", day="Tuesday", date="2026-11-10", time="09:00")
    taint = TaintLedger(
        early_first_fire=(("abc", "2026-11-10T09:00", "today"),),
        weekly_stored=(("abc", "Tuesday"),),
    )
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=_CAR))
    assert parts[1:] == [first, WEEKLY_STORED_NOTE.format(days="Tuesday")]
    assert DAILY_STORED_NOTE not in parts


async def test_the_loop_holds_a_rule_on_chosen_days_and_runs_the_call() -> None:
    ran: list[object] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return _STORED

    registry = InMemoryToolRegistry(
        {
            SCHEDULE_TOOL_NAME: (
                ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={}),
                handler,
            )
        }
    )
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, RecordingAuditSink(), TickingClock()),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_CAR,
    )
    working = [Message(role=Role.USER, text=_CAR, at=TickingClock().now(), turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=[_call()])
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert ran == [_WED]
    assert taint.weekly_stored == _HELD
