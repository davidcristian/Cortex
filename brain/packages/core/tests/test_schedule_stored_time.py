from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_claim import STORED_TIME_NOTE, names_time_of_day, stored_time
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME, SNOOZE_SCHEDULED_TOOL_NAME
from cortex_core.stops import StopLedger
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 6, 3, 0, 0, tzinfo=UTC)
_PARCEL = "Remind me on 14 December to post the parcel."
_MORNING = "scheduled reminder abc: due 2026-12-14T09:00:00+00:00 (in 38 days)"
_WEEKLY = "scheduled reminder abc: due 2026-11-09T09:00:00+00:00 (Monday), repeats weekly"
_SOON = "scheduled reminder abc: due 2026-11-06T03:10:00+00:00 (today)"
_MOVED = "edited abc: now due 2026-11-20T10:00:00+00:00"


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder for 14 December at 9:00 AM.",
        "I've set a reminder for 14 December at 09:00.",
        "I'll remind you at 9 am on 14 December.",
        "I'll remind you at 9 a.m.",
        "I'll remind you at 9AM.",
        "I'll remind you at noon on the 14th.",
        "I'll remind you at midnight.",
        "Je vous rappellerai d'appeler votre sœur demain à 17h30.",
        "Je vous le rappellerai à 9 h 15.",
        "Ich erinnere dich morgen um 9 Uhr.",
        "Ich erinnere dich um 9.30 Uhr an den Termin.",
    ],
)
def test_a_clock_figure_am_or_pm_noon_or_midnight_names_a_time_of_day(reply: str) -> None:
    assert names_time_of_day(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "I've set a reminder for 14 December to post the parcel.",
        "I'll remind you at nine in the morning on 14 December.",
        "I'll remind you on 14 December at 9.",
        "Set: a reminder every 4 weeks from 3 March.",
        "I'll remind you in 9 minutes.",
        "Mia's birthday on 9 August is set, every year.",
        "I made 5 amendments to the plan.",
        "I'll remind you in 2h.",
        "I'll remind you in 2h30.",
        "Je vous le rappellerai dans 2h30.",
        "Die Uhr im Flur geht 5 Minuten vor.",
        "Ich habe 3 Uhren gefunden.",
    ],
)
def test_a_reply_with_no_clock_figure_names_no_time_of_day(reply: str) -> None:
    assert not names_time_of_day(reply)


@pytest.mark.parametrize(
    ("name", "arguments", "result", "time"),
    [
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T09:00:00"}, _MORNING, "09:00"),
        (SCHEDULE_TOOL_NAME, {"at_time": "09:00", "on_days": ["mon"]}, _WEEKLY, "09:00"),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T00:00:00"}, _MORNING.replace("09", "00"), "00:00"),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "on_month_days": [20]}, _MOVED, "10:00"),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "gas"}, "edited abc", ""),
        (SCHEDULE_TOOL_NAME, {"in_seconds": 600}, _SOON, ""),
        (SCHEDULE_TOOL_NAME, {"every_seconds": 7200}, _SOON, ""),
        (SCHEDULE_TOOL_NAME, {"at": None, "at_time": None}, _MORNING, ""),
        (SCHEDULE_TOOL_NAME, {"at": "2026-12-14T09:00:00"}, "REFUSED: not run", ""),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "abc"}, "snoozed abc: now due 2026-11-06T10:00:00", ""),
        ("set_volume", {"at": "2026-12-14T09:00:00"}, _MORNING, ""),
    ],
)
def test_the_stored_time_is_read_from_a_timed_schedule_or_edit_result(
    name: str, arguments: Mapping[str, object], result: str, time: str
) -> None:
    assert stored_time(ToolCall(id="c", name=name, arguments=arguments), result) == time


def _closed(reply: str, time: str) -> str:
    parts = [reply]
    taint = TaintLedger(stored_time=time)
    runs = (ToolRun(name=SCHEDULE_TOOL_NAME, ok=True),)
    list(limit_notes(StopLedger(), runs, parts, caps=TurnCapabilities(), taint=taint, query=""))
    return "".join(parts)


@pytest.mark.parametrize(
    ("reply", "time", "noted"),
    [
        ("I've set a reminder for 14 December to post the parcel.", "09:00", True),
        ("I'll remind you at nine in the morning on 14 December.", "09:00", True),
        ("I'll remind you on 14 December at 9.", "09:00", True),
        ("Moved: the gas bill reminder is now on the 20th of every month.", "10:00", True),
        ("I've set a reminder for 14 December at 9:00 AM.", "09:00", False),
        ("I'll remind you at noon on the 14th.", "12:00", False),
        ("I'll remind you at midnight on 14 December.", "00:00", False),
        ("C'est fait ! Je vous rappellerai demain à 17h30.", "17:30", False),
        ("Alles klar, ich erinnere dich morgen um 9 Uhr.", "09:00", False),
        ("I've set a reminder for 14 December to post the parcel.", "", False),
    ],
)
def test_a_reply_naming_no_time_over_a_stored_time_gets_the_note(
    reply: str, time: str, *, noted: bool
) -> None:
    shown = _closed(reply, time)
    expected = reply + STORED_TIME_NOTE.format(time=time) if noted else reply
    assert shown == expected


async def _loop(calls: list[ToolCall]) -> TaintLedger:
    async def handler(arguments: Mapping[str, object]) -> str:
        return str(arguments["result"])

    tools = {
        name: (ToolSpec(name=name, description="s", parameters={}), handler)
        for name in (SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME)
    }
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(
            InMemoryToolRegistry(tools), RecordingAuditSink(), TickingClock()
        ),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_PARCEL,
    )
    working = [Message(role=Role.USER, text=_PARCEL, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return taint


_SET = ToolCall(
    id="c1", name=SCHEDULE_TOOL_NAME, arguments={"at": "2026-12-14T09:00:00", "result": _MORNING}
)
_EDIT = ToolCall(
    id="c2",
    name=EDIT_SCHEDULED_TOOL_NAME,
    arguments={"id": "abc", "on_month_days": [20], "result": _MOVED},
)
_RELATIVE = ToolCall(
    id="c3", name=SCHEDULE_TOOL_NAME, arguments={"in_seconds": 600, "result": _SOON}
)


@pytest.mark.parametrize(
    ("calls", "time"),
    [
        ([_SET], "09:00"),
        ([_SET, _EDIT], "10:00"),
        ([_SET, _RELATIVE], "09:00"),
        ([_RELATIVE], ""),
        ([], ""),
    ],
)
async def test_the_last_timed_call_that_ran_sets_the_stored_time(
    calls: list[ToolCall], time: str
) -> None:
    assert (await _loop(calls)).stored_time == time
