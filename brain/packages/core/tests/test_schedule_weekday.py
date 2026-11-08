from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo

import pytest
import swap_harness as harness
from swap_harness import Fakes, ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryHandoffStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    StopLedger,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEvent,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_time import UTC_DISPLAY, DisplayZone
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.schedule_weekday import (
    WEEKDAY_OFF_NOTE,
    WEEKDAY_OFF_NOTES,
    weekday_off,
    weekday_off_after,
    weekday_off_note,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 8, 3, 0, 0, tzinfo=UTC)
_DOCTOR = "Erinnere mich am Donnerstag um 7 Uhr an den Arzttermin."
_FRIDAY = {"text": "Arzttermin", "at": "2026-11-13T07:00:00"}
_THURSDAY = {"text": "Arzttermin", "at": "2026-11-12T07:00:00"}
_BINS = "Remind me at 6pm to put the bins out for Monday's collection."
_FOLLOW_UP = "Remind me at 9 to follow up on Monday's call."
_MUM = "Remind me Monday at 9pm to call mum."
_LOS_ANGELES = ZoneInfo("America/Los_Angeles")
_ENGLISH_FRIDAY = (
    "\n\n(A reminder set in this turn is on Friday 2026-11-13. Ask to move it if you meant "
    "another day.)"
)


def _ran(content: str = "scheduled", *, failed: bool = False) -> ToolResult:
    return ToolResult(call_id="c", content=content, trust=Trust.TRUSTED, is_error=failed)


@pytest.mark.parametrize(
    ("message", "at", "zone", "stored"),
    [
        (_DOCTOR, "2026-11-13T07:00:00", UTC, "2026-11-13"),
        (_DOCTOR, "2026-11-11T07:00:00", UTC, "2026-11-11"),
        (_DOCTOR, "2026-11-13T23:30:00", UTC, "2026-11-13"),
        (_DOCTOR, "2026-11-12T07:00:00", UTC, ""),
        (_DOCTOR, "2026-11-14T07:00:00", UTC, ""),
        (_DOCTOR, "2026-11-10T07:00:00", UTC, ""),
        (_FOLLOW_UP, "2026-11-10T09:00:00", UTC, "2026-11-10"),
        (_BINS, "2026-11-08T18:00:00", UTC, "2026-11-08"),
        (_BINS, "2026-11-09T18:00:00", UTC, ""),
        (
            "Erinnere mich jeden Donnerstag um 7 Uhr an den Arzttermin.",
            "2026-11-13T07:00:00",
            UTC,
            "",
        ),
        ("Remind me at 7 to call the doctor.", "2026-11-13T07:00:00", UTC, ""),
        (_MUM, "2026-11-10T05:00:00Z", _LOS_ANGELES, ""),
        (_MUM, "2026-11-10T05:00:00Z", UTC, "2026-11-10"),
        (_DOCTOR, "2026-11-14T05:00:00Z", _LOS_ANGELES, "2026-11-13"),
    ],
)
def test_a_one_time_date_a_day_off_the_named_weekday_is_read_in_the_persons_zone(
    *, message: str, at: str, zone: tzinfo, stored: str
) -> None:
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments={"text": "t", "at": at})
    assert weekday_off(call, _ran(), message, zone) == stored


@pytest.mark.parametrize(
    ("name", "arguments", "failed"),
    [
        (SCHEDULE_TOOL_NAME, _FRIDAY, True),
        (SCHEDULE_TOOL_NAME, {**_FRIDAY, "at_time": "07:00"}, False),
        (SCHEDULE_TOOL_NAME, {**_FRIDAY, "every_seconds": 86400}, False),
        (SCHEDULE_TOOL_NAME, {"text": "t", "in_seconds": 3600}, False),
        (SCHEDULE_TOOL_NAME, {"text": "t", "at": 7}, False),
        (SCHEDULE_TOOL_NAME, {"text": "t", "at": "Friday at 7"}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", **_FRIDAY}, True),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", "at_time": "07:00"}, False),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "i", **_FRIDAY}, False),
    ],
)
def test_a_call_that_stored_no_dated_one_time_item_is_never_read(
    *, name: str, arguments: Mapping[str, object], failed: bool
) -> None:
    call = ToolCall(id="c", name=name, arguments=arguments)
    assert weekday_off(call, _ran(failed=failed), _DOCTOR, UTC) == ""


@pytest.mark.parametrize(
    ("at", "stored"), [("2026-11-13T07:00:00", "2026-11-13"), ("2026-11-12T07:00:00", "")]
)
def test_an_edit_that_moved_an_item_with_at_is_read_as_a_store(*, at: str, stored: str) -> None:
    call = ToolCall(id="c", name=EDIT_SCHEDULED_TOOL_NAME, arguments={"id": "i", "at": at})
    assert weekday_off(call, _ran("edited i: now due x"), _DOCTOR, UTC) == stored


_HELD = ("abc", "2026-11-13")


def _after(
    name: str, arguments: Mapping[str, object], content: str = "ok", *, failed: bool = False
) -> tuple[str, str]:
    call = ToolCall(id="c", name=name, arguments=arguments)
    return weekday_off_after(call, _ran(content, failed=failed), _DOCTOR, UTC, _HELD)


@pytest.mark.parametrize(
    ("content", "held"),
    [
        ("scheduled reminder xyz: due Fri 13 Nov 07:00 UTC", ("xyz", "2026-11-13")),
        ("scheduled", ("", "2026-11-13")),
    ],
)
def test_a_store_a_day_off_keeps_the_id_its_result_names(
    *, content: str, held: tuple[str, str]
) -> None:
    call = ToolCall(id="c", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    assert weekday_off_after(call, _ran(content), _DOCTOR, UTC, ("", "")) == held


def test_a_move_a_day_off_replaces_the_held_pair_with_the_moved_item() -> None:
    moved = {"id": "def", "at": "2026-11-11T07:00:00"}
    assert _after(EDIT_SCHEDULED_TOOL_NAME, moved) == ("def", "2026-11-11")


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at": "2026-11-12T07:00:00"}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "07:00"}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "on_days": ["thu"]}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "t", "every_seconds": 0}),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "abc"}),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "abc", "for_seconds": 600}),
    ],
)
def test_a_later_change_to_the_held_items_due_time_drops_the_date(
    *, name: str, arguments: Mapping[str, object]
) -> None:
    assert _after(name, arguments) == ("", "")


@pytest.mark.parametrize(
    ("name", "arguments", "failed"),
    [
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "t", "at_time": None}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "def", "at": "2026-11-12T07:00:00"}, False),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "def"}, False),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "def", "for_seconds": 600}, False),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "abc"}, True),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at": "2026-11-12T07:00:00"}, True),
        ("list_scheduled", {"id": "abc"}, False),
    ],
)
def test_a_call_that_leaves_the_held_items_due_time_keeps_the_date(
    *, name: str, arguments: Mapping[str, object], failed: bool
) -> None:
    assert _after(name, arguments, failed=failed) == _HELD


def test_a_change_to_any_item_drops_a_date_held_with_no_id() -> None:
    call = ToolCall(id="c", name=CANCEL_SCHEDULED_TOOL_NAME, arguments={"id": "def"})
    assert weekday_off_after(call, _ran(), _DOCTOR, UTC, ("", "2026-11-13")) == ("", "")


@pytest.mark.parametrize(
    ("language", "named"),
    [
        ("en", "on Friday 2026-11-13."),
        ("fr", "au vendredi 2026-11-13."),
        ("de", "auf Freitag, 2026-11-13 gestellt."),
        ("es", "para el viernes 2026-11-13."),
        ("ro", "pentru vineri, 2026-11-13."),
    ],
)
def test_the_note_names_the_stored_weekday_and_date_in_the_language_of_the_message(
    *, language: str, named: str
) -> None:
    note = weekday_off_note("2026-11-13", language)
    assert named in note
    assert note.startswith("\n\n(")
    assert note.endswith(")")


def test_the_english_note_is_the_plain_sentence() -> None:
    assert weekday_off_note("2026-11-13", "en") == _ENGLISH_FRIDAY
    assert WEEKDAY_OFF_NOTE.format(day="Friday", date="2026-11-13") == _ENGLISH_FRIDAY


async def _loop(
    query: str, calls: list[ToolCall], zone: DisplayZone = UTC_DISPLAY
) -> tuple[list[object], TaintLedger]:
    ran: list[object] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "scheduled reminder abc: due later"

    registry = InMemoryToolRegistry(
        {
            name: (ToolSpec(name=name, description="s", parameters={}), handler)
            for name in (SCHEDULE_TOOL_NAME, EDIT_SCHEDULED_TOOL_NAME, CANCEL_SCHEDULED_TOOL_NAME)
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
        query=query,
        zone=zone,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=calls)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return ran, taint


async def test_a_date_a_day_off_the_named_weekday_runs_and_is_kept_for_the_note() -> None:
    late = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    ran, taint = await _loop(_DOCTOR, [late])
    assert ran == [_FRIDAY]
    assert taint.weekday_off == "2026-11-13"


async def test_a_later_store_on_the_named_weekday_keeps_the_earlier_date_a_day_off() -> None:
    late = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    right = ToolCall(id="c2", name=SCHEDULE_TOOL_NAME, arguments={**_THURSDAY, "text": "b"})
    ran, taint = await _loop(_DOCTOR, [late, right])
    assert ran == [_FRIDAY, {**_THURSDAY, "text": "b"}]
    assert taint.weekday_off == "2026-11-13"


async def test_the_date_is_kept_beside_the_id_its_store_named() -> None:
    late = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    _, taint = await _loop(_DOCTOR, [late])
    assert (taint.weekday_off_id, taint.weekday_off) == ("abc", "2026-11-13")


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at": "2026-11-12T07:00:00"}),
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "abc"}),
    ],
)
async def test_a_later_move_or_cancel_in_the_turn_drops_the_date_the_store_no_longer_holds(
    *, name: str, arguments: Mapping[str, object]
) -> None:
    late = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    later = ToolCall(id="c2", name=name, arguments=arguments)
    ran, taint = await _loop(_DOCTOR, [late, later])
    assert ran == [_FRIDAY, arguments]
    assert (taint.weekday_off_id, taint.weekday_off) == ("", "")


async def test_a_move_a_day_off_in_the_turn_is_kept_for_the_note() -> None:
    moved = {"id": "abc", "at": "2026-11-13T07:00:00"}
    _, taint = await _loop(
        _DOCTOR, [ToolCall(id="c1", name=EDIT_SCHEDULED_TOOL_NAME, arguments=moved)]
    )
    assert (taint.weekday_off_id, taint.weekday_off) == ("abc", "2026-11-13")


async def test_a_date_on_the_named_weekday_runs_and_keeps_no_date() -> None:
    right = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_THURSDAY)
    ran, taint = await _loop(_DOCTOR, [right])
    assert ran == [_THURSDAY]
    assert taint.weekday_off == ""


@pytest.mark.parametrize(
    ("query", "ending"),
    [
        (_DOCTOR, "auf Freitag, 2026-11-13 gestellt. Bitten Sie um eine Verschiebung"),
        (_BINS, "on Friday 2026-11-13. Ask to move it if you meant another day.)"),
    ],
)
def test_a_turn_that_kept_a_date_closes_with_the_note_in_the_language_of_the_message(
    *, query: str, ending: str
) -> None:
    parts = ["Done."]
    taint = TaintLedger(weekday_off="2026-11-13")
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query))
    assert ending in "".join(parts)


def test_a_turn_that_kept_no_date_has_no_note() -> None:
    parts = ["Done."]
    list(
        limit_notes(
            StopLedger(), (), parts, caps=TurnCapabilities(), taint=TaintLedger(), query=_DOCTOR
        )
    )
    assert parts == ["Done."]


def _shown(events: Sequence[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_the_date_survives_the_model_swap_through_the_handoff_store() -> None:
    slot = harness.prepared_slot(taint=TaintLedger(weekday_off="2026-11-13", weekday_off_id="a"))
    store = InMemoryHandoffStore()
    await store.put(
        slot.snapshot(turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT)
    )
    loaded = await store.get(harness.TURN)
    assert loaded is not None
    assert loaded.taint_ledger().weekday_off == "2026-11-13"
    assert loaded.taint_ledger().weekday_off_id == "a"
    live = harness.build_harness()
    await live.seed_session()
    shown = _shown(await harness.run_handoff(live, slot))
    assert shown.endswith(_ENGLISH_FRIDAY)


def _dispatcher() -> ToolDispatcher:
    async def handler(_arguments: Mapping[str, object]) -> str:
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    return ToolDispatcher(registry, RecordingAuditSink(), TickingClock())


async def test_a_deep_store_a_day_off_the_named_weekday_runs_and_shows_the_note() -> None:
    deep = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_FRIDAY)
    live = harness.build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("done",), tool_calls=(deep,))),
        capabilities=TurnCapabilities(tools=_dispatcher()),
    )
    await live.sessions.append(
        harness.SESSION, Message(role=Role.USER, text=_DOCTOR, at=_AT, turn_id=harness.TURN)
    )
    shown = _shown(await harness.run_handoff(live, harness.prepared_slot()))
    assert "auf Freitag, 2026-11-13 gestellt" in shown


@pytest.mark.parametrize(
    ("language", "opening"),
    [
        ("fr", "(Un rappel créé ici"),
        ("de", "(Eine hier erstellte Erinnerung"),
        ("es", "(Un recordatorio creado aquí"),
        ("ro", "(Un memento creat aici"),
    ],
)
def test_a_translated_note_names_one_reminder_of_the_turn(language: str, opening: str) -> None:
    assert WEEKDAY_OFF_NOTES[language].removeprefix("\n\n").startswith(opening)
