from collections.abc import Mapping
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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
from cortex_core.schedule_first_fire import (
    FIRST_FIRE_NOTE,
    days_named,
    early_first_fire,
    early_first_fire_after,
    early_first_fire_notes,
)
from cortex_core.schedule_time import DisplayZone
from cortex_core.schedule_verbs import CANCEL_SCHEDULED_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_BERLIN = ZoneInfo("Europe/Berlin")
_NOW = datetime(2026, 11, 10, 5, 30, tzinfo=UTC)
_TODAY = "scheduled reminder abc: due 2026-11-10T09:00:00+01:00 (today), every day at 09:00"
_TOMORROW = "scheduled reminder abc: due 2026-11-11T09:00:00+01:00 (tomorrow), every day at 09:00"
_ONCE = "scheduled reminder abc: due 2026-11-11T09:00:00+01:00 (tomorrow)"
_CAR = "Remember that I park on level 3 and remind me tomorrow at 9 to move the car."
_DAILY = {"kind": "reminder", "text": "move the car", "at_time": "09:00"}
_NOTE = (
    "\n\n(A reminder set or changed in this turn first fires today, Tuesday 2026-11-10 at 09:00. "
    "Ask to change its first day if you meant a later one.)"
)
_EDITED = "edited abc: now due 2026-11-10T09:30:00+01:00"


def _ran(content: str, *, failed: bool = False) -> ToolResult:
    return ToolResult(call_id="c", content=content, trust=Trust.TRUSTED, is_error=failed)


def _store(arguments: Mapping[str, object] = _DAILY) -> ToolCall:
    return ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)


@pytest.mark.parametrize(
    ("message", "arguments", "content", "expected"),
    [
        (_CAR, _DAILY, _TODAY, ("2026-11-10T09:00", 0)),
        (
            "Read notes.txt and remind me tomorrow at 9 of the first item in it.",
            _DAILY,
            _TODAY,
            ("2026-11-10T09:00", 0),
        ),
        (
            "Souviens-toi que le code de mon casier est 4417 et rappelle-moi demain à 9h de vider "
            "le casier.",
            _DAILY,
            _TODAY,
            ("2026-11-10T09:00", 0),
        ),
        ("Erinnere mich morgen um 9 an das Auto.", _DAILY, _TODAY, ("2026-11-10T09:00", 0)),
        (
            "Recuérdame mañana por la mañana a las 9 mover el coche.",
            _DAILY,
            _TODAY,
            ("2026-11-10T09:00", 0),
        ),
        ("Amintește-mi mâine la ora 9 de mașină.", _DAILY, _TODAY, ("2026-11-10T09:00", 0)),
        (
            "Remind me every day at 9 starting tomorrow to move the car.",
            {**_DAILY, "starting": "2026-11-11"},
            _TOMORROW,
            ("", 0),
        ),
        (
            "Remind me every day at 9 starting tomorrow to move the car.",
            _DAILY,
            _TODAY,
            ("2026-11-10T09:00", 0),
        ),
        ("Remind me at 9 to move the car.", _DAILY, _TODAY, ("", 0)),
        ("Remind me every day at 9 starting today to move the car.", _DAILY, _TODAY, ("", 0)),
        ("Remind me Tuesday at 9 to move the car.", _DAILY, _TODAY, ("", 0)),
        ("Recuérdame cada día a las 9 de la mañana mover el coche.", _DAILY, _TODAY, ("", 0)),
        ("Erinnere mich jeden Morgen um 9 an das Auto.", _DAILY, _TODAY, ("", 0)),
        (_CAR, {"kind": "reminder", "text": "car", "at": "2026-11-11T09:00:00"}, _ONCE, ("", 0)),
        (
            _CAR,
            {"kind": "reminder", "text": "car", "at": "2026-11-10T09:00:00"},
            "scheduled reminder abc: due 2026-11-10T09:00:00+01:00 (today)",
            ("", 0),
        ),
        (_CAR, _DAILY, _TOMORROW, ("", 0)),
        (
            "Remind me the day after tomorrow at 9 to move the car.",
            _DAILY,
            _TOMORROW,
            ("2026-11-11T09:00", 1),
        ),
        ("Rappelle-moi après-demain à 9h.", _DAILY, _TODAY, ("2026-11-10T09:00", 0)),
        (
            "Remind me Friday at 9 to call the doctor.",
            {**_DAILY, "on_days": ["thursday"]},
            "scheduled reminder abc: due 2026-11-12T09:00:00+01:00 (in 2 days), on Thursday",
            ("2026-11-12T09:00", 2),
        ),
        (
            _CAR,
            _DAILY,
            "scheduled reminder abc: due 2026-11-10T09:00:00",
            ("2026-11-10T09:00", 0),
        ),
        (_CAR, _DAILY, "scheduled reminder abc: due 2026-13-40T09:00:00", ("", 0)),
        (_CAR, _DAILY, "scheduled reminder abc", ("", 0)),
    ],
)
def test_a_repeat_first_firing_before_the_named_day_is_read_with_its_first_fire(
    *, message: str, arguments: Mapping[str, object], content: str, expected: tuple[str, int]
) -> None:
    assert early_first_fire(_store(arguments), _ran(content), message, _NOW, _BERLIN) == expected


def test_a_failed_store_or_another_tool_reads_no_first_fire() -> None:
    cancel = ToolCall(id="c1", name=CANCEL_SCHEDULED_TOOL_NAME, arguments={"id": "abc"})
    assert early_first_fire(_store(), _ran(_TODAY, failed=True), _CAR, _NOW, _BERLIN) == ("", 0)
    assert early_first_fire(cancel, _ran(_TODAY), _CAR, _NOW, _BERLIN) == ("", 0)


@pytest.mark.parametrize(
    ("arguments", "content", "expected"),
    [
        ({"id": "abc", "at_time": "09:30"}, _EDITED, ("2026-11-10T09:30", 0)),
        ({"id": "abc", "on_days": ["tuesday"]}, _EDITED, ("2026-11-10T09:30", 0)),
        (
            {"id": "abc", "at_time": "09:30", "starting": "2026-11-11"},
            "edited abc: now due 2026-11-11T09:30:00+01:00",
            ("", 0),
        ),
        ({"id": "abc", "every_seconds": 3600}, _EDITED, ("", 0)),
        ({"id": "abc", "at": "2026-11-10T09:30:00"}, _EDITED, ("", 0)),
        ({"id": "abc", "at_time": "09:30"}, "edited abc", ("", 0)),
    ],
)
def test_an_edit_moving_a_repeat_before_the_named_day_is_read_with_its_first_fire(
    *, arguments: Mapping[str, object], content: str, expected: tuple[str, int]
) -> None:
    edit = ToolCall(id="c2", name=EDIT_SCHEDULED_TOOL_NAME, arguments=arguments)
    assert early_first_fire(edit, _ran(content), _CAR, _NOW, _BERLIN) == expected


def test_a_store_re_timed_to_another_early_time_keeps_one_first_fire() -> None:
    held = early_first_fire_after(_store(), _ran(_TODAY), _CAR, _NOW, _BERLIN, ())
    edit = ToolCall(
        id="c2", name=EDIT_SCHEDULED_TOOL_NAME, arguments={"id": "abc", "at_time": "09:30"}
    )
    after = early_first_fire_after(edit, _ran(_EDITED), _CAR, _NOW, _BERLIN, held)
    assert after == (("abc", "2026-11-10T09:30", 0),)


def test_a_daily_store_beside_a_weekday_and_a_change_verb_is_read_with_its_first_fire() -> None:
    message = "Remind me Friday at 9 to move the car."
    expected = ("2026-11-10T09:00", 0)
    assert early_first_fire(_store(), _ran(_TODAY), message, _NOW, _BERLIN) == expected


def test_a_store_after_nine_first_fires_on_the_named_day() -> None:
    late = datetime(2026, 11, 10, 8, 30, tzinfo=UTC)
    assert early_first_fire(_store(), _ran(_TOMORROW), _CAR, late, _BERLIN) == ("", 0)


@pytest.mark.parametrize(
    ("message", "days"),
    [
        ("tomorrow at 9", 1),
        ("the day after tomorrow", 2),
        ("pasado mañana", 2),
        ("übermorgen", 2),
        ("morgen Morgen um 9", 1),
        ("heute Morgen um 9", 0),
        ("at 9", 0),
        ("on Thursday at 9", 2),
        ("on Monday at 9", 6),
        ("Remind me Friday at 9 to move the car.", 3),
        ("Remind me Friday at 9 to call Anna again.", 3),
        ("Remind me every Friday at 9 to move the car.", 3),
        ("Move my Friday reminder to Monday.", 0),
        ("Remind me every day until Friday at 8.", 3),
    ],
)
def test_the_named_day_is_counted_from_today(*, message: str, days: int) -> None:
    assert days_named(message, _NOW.date()) == days


def test_a_store_first_firing_early_is_kept_and_a_cancel_of_it_drops_it() -> None:
    held = early_first_fire_after(_store(), _ran(_TODAY), _CAR, _NOW, _BERLIN, ())
    assert held == (("abc", "2026-11-10T09:00", 0),)
    failed = early_first_fire_after(_store(), _ran("", failed=True), _CAR, _NOW, _BERLIN, held)
    assert failed == held
    cancel = ToolCall(id="c2", name=CANCEL_SCHEDULED_TOOL_NAME, arguments={"id": "abc"})
    assert early_first_fire_after(cancel, _ran("cancelled"), _CAR, _NOW, _BERLIN, held) == ()


@pytest.mark.parametrize(
    ("arguments", "kept"),
    [
        ({"id": "abc", "every_seconds": 0}, True),
        ({"id": "abc", "text": "move it"}, True),
        ({"id": "abc", "at": "2026-11-11T09:00:00"}, False),
        ({"id": "abc", "at_time": "09:00", "starting": "2026-11-11"}, False),
    ],
)
def test_an_edit_keeps_the_first_fire_unless_it_moves_the_due_time(
    *, arguments: Mapping[str, object], kept: bool
) -> None:
    held = (("abc", "2026-11-10T09:00", 0),)
    edit = ToolCall(id="c2", name=EDIT_SCHEDULED_TOOL_NAME, arguments=arguments)
    after = early_first_fire_after(edit, _ran("edited abc"), _CAR, _NOW, _BERLIN, held)
    assert after == (held if kept else ())


def test_each_first_fire_has_one_note_and_a_repeated_one_none_more() -> None:
    held = (
        ("a", "2026-11-10T09:00", 0),
        ("b", "2026-11-12T08:30", 2),
        ("c", "2026-11-10T09:00", 0),
    )
    second = FIRST_FIRE_NOTE.format(
        when="in 2 days", day="Thursday", date="2026-11-12", time="08:30"
    )
    assert early_first_fire_notes(held) == (_NOTE, second)


def test_a_turn_holding_an_early_first_fire_closes_with_the_note_after_the_daily_note() -> None:
    parts = ["I'll remind you tomorrow at 9:00 AM."]
    taint = TaintLedger(daily_stored=("abc",), early_first_fire=(("abc", "2026-11-10T09:00", 0),))
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=_CAR))
    assert parts[1:] == [DAILY_STORED_NOTE, _NOTE]


async def test_the_loop_keeps_a_store_first_firing_before_the_named_day_and_runs_it() -> None:
    ran: list[object] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled reminder abc: due 2026-07-25T15:00:00+02:00 (today), every day at 15:00"

    registry = InMemoryToolRegistry(
        {
            SCHEDULE_TOOL_NAME: (
                ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={}),
                handler,
            )
        }
    )
    taint = TaintLedger()
    query = "Remind me tomorrow at 3pm to call Anna."
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, RecordingAuditSink(), TickingClock()),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=query,
        zone=DisplayZone(name="Europe/Berlin", tz=_BERLIN),
    )
    working = [Message(role=Role.USER, text=query, at=_NOW, turn_id="t")]
    arguments = {"kind": "reminder", "text": "call Anna", "at_time": "15:00"}
    backend = ScriptedBrainBackend(
        chunks=("done",),
        tool_calls=[ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=arguments)],
    )
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert ran == [arguments]
    assert taint.early_first_fire == (("abc", "2026-07-25T15:00", 0),)
