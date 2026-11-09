from collections.abc import Mapping
from datetime import UTC, datetime

import pytest
from swap_harness import ScriptedBrainBackend, TickingClock

from cortex_core import (
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
from cortex_core.schedule_made_repeating import (
    MADE_REPEATING_NOTE,
    MADE_REPEATING_NOTES,
    made_repeating_after,
)
from cortex_core.schedule_verbs import (
    CANCEL_SCHEDULED_TOOL_NAME,
    EDIT_SCHEDULED_TOOL_NAME,
    SNOOZE_SCHEDULED_TOOL_NAME,
)
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 9, 3, 0, 0, tzinfo=UTC)
_MOVE = "Move my dentist reminder to Tuesday at 15:00."
_WEEKLY = {"id": "abc", "at_time": "15:00", "on_days": ["tue"], "repeat": True}


def _after(
    name: str, arguments: Mapping[str, object], held: tuple[str, ...] = (), *, failed: bool = False
) -> tuple[str, ...]:
    call = ToolCall(id="c", name=name, arguments=arguments)
    result = ToolResult(call_id="c", content="edited", trust=Trust.TRUSTED, is_error=failed)
    return made_repeating_after(call, result, held)


@pytest.mark.parametrize(
    "selector",
    [{"on_days": ["tue"]}, {"on_month_days": [10]}, {"on_dates": ["11-10"]}],
)
def test_an_edit_with_repeat_at_time_and_days_is_held(selector: Mapping[str, object]) -> None:
    arguments = {"id": "abc", "at_time": "15:00", "repeat": True, **selector}
    assert _after(EDIT_SCHEDULED_TOOL_NAME, arguments) == ("abc",)


def test_an_item_made_repeating_twice_is_held_once() -> None:
    assert _after(EDIT_SCHEDULED_TOOL_NAME, _WEEKLY, ("abc",)) == ("abc",)
    assert _after(EDIT_SCHEDULED_TOOL_NAME, {**_WEEKLY, "id": "def"}, ("abc",)) == ("abc", "def")


@pytest.mark.parametrize(
    ("name", "arguments", "failed"),
    [
        (EDIT_SCHEDULED_TOOL_NAME, {**_WEEKLY, "repeat": False}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "15:00", "on_days": ["tue"]}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "on_days": ["tue"], "repeat": True}, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "15:00", "repeat": True}, False),
        (EDIT_SCHEDULED_TOOL_NAME, _WEEKLY, True),
        (EDIT_SCHEDULED_TOOL_NAME, {**_WEEKLY, "id": 7}, False),
        (SNOOZE_SCHEDULED_TOOL_NAME, _WEEKLY, False),
    ],
)
def test_a_call_that_made_nothing_repeat_on_days_holds_nothing(
    *, name: str, arguments: Mapping[str, object], failed: bool
) -> None:
    assert _after(name, arguments, failed=failed) == ()


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "abc"}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "every_seconds": 0}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "16:00"}),
    ],
)
def test_a_cancel_an_interval_or_a_daily_time_drops_the_item(
    *, name: str, arguments: Mapping[str, object]
) -> None:
    assert _after(name, arguments, ("abc", "def")) == ("def",)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        (CANCEL_SCHEDULED_TOOL_NAME, {"id": "xyz"}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "text": "dentist"}),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "abc", "at_time": "16:00", "on_days": ["wed"]}),
        (SNOOZE_SCHEDULED_TOOL_NAME, {"id": "abc", "for_seconds": 600}),
    ],
)
def test_a_call_that_leaves_the_rule_on_days_keeps_the_item(
    *, name: str, arguments: Mapping[str, object]
) -> None:
    assert _after(name, arguments, ("abc",)) == ("abc",)


async def test_a_turn_whose_edit_made_a_reminder_repeat_holds_its_id() -> None:
    ran: list[object] = []

    async def handler(arguments: Mapping[str, object]) -> str:
        ran.append(dict(arguments))
        return "edited abc: now due Tue 10 Nov 15:00 UTC"

    spec = ToolSpec(name=EDIT_SCHEDULED_TOOL_NAME, description="e", parameters={})
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(
            InMemoryToolRegistry({EDIT_SCHEDULED_TOOL_NAME: (spec, handler)}),
            RecordingAuditSink(),
            TickingClock(),
        ),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_MOVE,
    )
    call = ToolCall(id="c1", name=EDIT_SCHEDULED_TOOL_NAME, arguments=_WEEKLY)
    working = [Message(role=Role.USER, text=_MOVE, at=_AT, turn_id="t")]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=(call,))
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    assert ran == [_WEEKLY]
    assert taint.made_repeating == ("abc",)


def _closed(reply: str, made: tuple[str, ...], query: str = _MOVE) -> str:
    parts = [reply]
    taint = TaintLedger(made_repeating=made)
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("query", "note"),
    [
        (_MOVE, MADE_REPEATING_NOTE),
        (
            "Verschiebe meine Zahnarzt-Erinnerung auf Dienstag um 15 Uhr.",
            MADE_REPEATING_NOTES["de"],
        ),
    ],
)
def test_a_reply_naming_no_repeat_closes_with_the_note_in_the_language_of_the_message(
    *, query: str, note: str
) -> None:
    assert _closed("I moved it to Tuesday at 15:00.", ("abc",), query) == (
        "I moved it to Tuesday at 15:00." + note
    )


@pytest.mark.parametrize(
    ("reply", "made"),
    [("It now repeats every Tuesday at 15:00.", ("abc",)), ("I moved it to Tuesday.", ())],
)
def test_a_reply_stating_the_repeat_or_a_turn_that_made_none_has_no_note(
    *, reply: str, made: tuple[str, ...]
) -> None:
    assert _closed(reply, made) == reply


def test_the_english_note_is_the_plain_sentence() -> None:
    assert MADE_REPEATING_NOTE == (
        "\n\n(This reminder now repeats. Ask to make it one time again if you meant only once.)"
    )


@pytest.mark.parametrize(
    ("language", "opening"),
    [
        ("fr", "(Ce rappel se répète désormais."),
        ("de", "(Diese Erinnerung wiederholt sich jetzt."),
        ("es", "(Este recordatorio ahora se repite."),
        ("ro", "(Acest memento se repetă acum."),
    ],
)
def test_each_translated_note_states_the_repeat_and_closes_its_bracket(
    *, language: str, opening: str
) -> None:
    note = MADE_REPEATING_NOTES[language]
    assert note.removeprefix("\n\n").startswith(opening)
    assert note.endswith(".)")
