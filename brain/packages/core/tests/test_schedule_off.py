import pytest

from cortex_core import TaintLedger, ToolRun, TurnCapabilities
from cortex_core.closing_notes import limit_notes
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.schedule_claim import UNSCHEDULED_CLAIM_NOTE
from cortex_core.schedule_off import REMINDERS_OFF_NOTE, REMINDERS_OFF_NOTES
from cortex_core.stops import StopLedger

_OFF = TurnCapabilities(reminders_off=True)


def _closed(
    query: str,
    reply: str,
    *,
    caps: TurnCapabilities = _OFF,
    earlier: tuple[ToolRun, ...] = (),
) -> str:
    parts = [reply]
    list(
        limit_notes(
            StopLedger(), (), parts, caps=caps, taint=TaintLedger(), query=query, earlier=earlier
        )
    )
    return "".join(parts)


@pytest.mark.parametrize(
    ("query", "reply", "note"),
    [
        (
            "Amintește-mi mâine la ora 9 să sun la dentist.",
            "Voi reține să te reamintesc mâine la ora 9:00.",
            REMINDERS_OFF_NOTES["ro"],
        ),
        (
            "Rappelle-moi demain à 9 heures d'appeler le dentiste.",
            "Je ne peux pas créer de rappel.",
            REMINDERS_OFF_NOTES["fr"],
        ),
        (
            "Remind me tomorrow at 9 to call the dentist.",
            "Sure, I will remind you tomorrow at 9.",
            REMINDERS_OFF_NOTE,
        ),
        (
            "Erinnere mich morgen um 9 an den Zahnarzt.",
            "Ich werde dich morgen um 9 erinnern.",
            REMINDERS_OFF_NOTES["de"],
        ),
        (
            "Recuérdame mañana a las 9 llamar al dentista.",
            "Te lo recordaré mañana a las 9.",
            REMINDERS_OFF_NOTES["es"],
        ),
    ],
)
def test_a_reminder_request_with_no_store_closes_with_the_note_in_its_language(
    query: str, reply: str, note: str
) -> None:
    assert _closed(query, reply) == reply + note


def test_a_reminder_request_with_a_store_gets_no_reminders_off_note() -> None:
    reply = "Sure, I will remind you tomorrow at 9."
    closed = _closed("Remind me tomorrow at 9 to call the dentist.", reply, caps=TurnCapabilities())
    assert closed == reply


@pytest.mark.parametrize(
    "query",
    [
        "What is the capital of Portugal, and roughly how many people live there?",
        "Write me a two line poem about Monday mornings.",
    ],
)
def test_a_message_naming_no_reminder_gets_no_note_with_no_store(query: str) -> None:
    assert _closed(query, "Lisbon.") == "Lisbon."


def test_a_claimed_reminder_with_no_store_gets_this_note_and_not_the_claim_note() -> None:
    reply = "I have set a reminder for tomorrow at 9."
    closed = _closed("Book the dentist for tomorrow at 9.", reply)
    assert closed == reply + REMINDERS_OFF_NOTE
    assert UNSCHEDULED_CLAIM_NOTE not in closed


def test_the_deep_phase_repeats_the_note_only_on_a_claim() -> None:
    handed = (ToolRun(name=ESCALATE_TOOL_NAME, ok=True),)
    query = "Remind me tomorrow at 9 to call the dentist."
    assert _closed(query, "The deep answer.", earlier=handed) == "The deep answer."
    claimed = "I have set a reminder for tomorrow at 9."
    assert _closed(query, claimed, earlier=handed) == claimed + REMINDERS_OFF_NOTE
