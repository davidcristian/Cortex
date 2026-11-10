import pytest

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_quoted import QUOTED_STORED_NOTE, quoted_request_only, quoted_stored_notes
from cortex_core.stops import StopLedger

_ANNA = (
    'Anna said: "remind me every day at 8 to water the plants". Can you note that she likes plants?'
)
_STORED = ToolRun(name=SCHEDULE_TOOL_NAME, ok=True)
_DAILY_NOTE = QUOTED_STORED_NOTE.format(what="A daily reminder at 08:00")


@pytest.mark.parametrize(
    "message",
    [
        _ANNA,
        'Anna said: "remind me every day at 8 to water the plants',
        "Anna m'a dit « rappelle-moi demain à 9 h ». Elle aime les plantes.",
        "Anna sagte „erinnere mich morgen um 9“. Sie mag Pflanzen.",
        "Anna sagte »erinnere mich morgen«, und sie mag Pflanzen.",
        "Ana dijo “recuérdame mañana”. Le gustan las plantas.",
        "Ana a spus „amintește-mi mâine”. Îi plac plantele.",
        '"Remind me at 8," I told myself.',
    ],
)
def test_a_request_to_remind_only_inside_quotation_marks_is_read(message: str) -> None:
    assert quoted_request_only(message)


@pytest.mark.parametrize(
    "message",
    [
        'Remind me at 8 to "water the plants".',
        'Remind me to answer Anna\'s "call me at 8".',
        'Anna said "I love plants". Remind me to buy her one tomorrow.',
        'Anna said "I love plants". Note that she likes plants.',
        'Anna said "remind me at 8". Set the same reminder for me.',
        'Wake me at 7 and add "remind Anna" to my list.',
        "Remind me every day at 8 to water the plants.",
        "Anna's plants need water, remind me at 8.",
        "Ana dijo “llama a las 8”. Recuérdame mañana.",
        "Anna a dit « appelle-moi », réveille-moi à 7 h.",
        '"Remind me every day at 8 to water the plants."',
        '"Remind me at 8." 9:30',
    ],
)
def test_a_request_outside_the_quotes_or_none_inside_them_is_not_read(message: str) -> None:
    assert not quoted_request_only(message)


@pytest.mark.parametrize(
    ("daily", "time", "what"),
    [
        (True, "08:00", "A daily reminder at 08:00"),
        (False, "09:30", "A reminder at 09:30"),
        (True, "", "A daily reminder"),
        (False, "", "A reminder"),
    ],
)
def test_the_note_names_the_repeat_and_time_the_turn_stored(
    *, daily: bool, time: str, what: str
) -> None:
    notes = quoted_stored_notes((_STORED,), _ANNA, daily=daily, time=time)
    assert notes == (QUOTED_STORED_NOTE.format(what=what),)


@pytest.mark.parametrize(
    ("runs", "message"),
    [
        ((), _ANNA),
        ((ToolRun(name=SCHEDULE_TOOL_NAME, ok=False),), _ANNA),
        ((ToolRun(name="list_scheduled", ok=True),), _ANNA),
        ((_STORED,), "Remind me every day at 8 to water the plants."),
    ],
)
def test_no_note_without_a_store_or_with_a_request_outside_the_quotes(
    *, runs: tuple[ToolRun, ...], message: str
) -> None:
    assert quoted_stored_notes(runs, message, daily=True, time="08:00") == ()


def _shown(
    runs: tuple[ToolRun, ...], message: str, reply: str, earlier: tuple[ToolRun, ...] = ()
) -> str:
    caps = TurnCapabilities(
        memory=MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    )
    taint = TaintLedger(daily_stored=("abc",), stored_time="08:00")
    parts = [reply]
    list(
        limit_notes(
            StopLedger(), runs, parts, caps=caps, taint=taint, query=message, earlier=earlier
        )
    )
    return "".join(parts)


def test_a_turn_storing_a_quoted_request_closes_with_the_note() -> None:
    reply = "I've set a daily reminder at 8:00 every day to water the plants."
    assert _shown((_STORED,), _ANNA, reply) == reply + _DAILY_NOTE


def test_a_turn_storing_the_persons_own_request_closes_without_the_note() -> None:
    reply = "I've set a daily reminder at 8:00 every day to water the plants."
    message = "Remind me every day at 8 to water the plants."
    assert _shown((_STORED,), message, reply) == reply


def test_a_store_before_a_handoff_closes_the_deep_reply_with_the_note() -> None:
    reply = "I've set a daily reminder at 8:00 every day to water the plants."
    assert _shown((), _ANNA, reply, earlier=(_STORED,)) == reply + _DAILY_NOTE
