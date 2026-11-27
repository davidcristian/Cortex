import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_kept_sentence import KEPT_CLAIM_NOTE, unnamed_sentence
from cortex_core.forget_unnamed import KEPT_NOTE
from cortex_core.stops import StopLedger

_PHONE = (
    "User: Remember that my phone is 0721 555 4242. Assistant: I've noted that your phone number "
    "is 0721 555 4242."
)
_LOCKER = "User: Remember that my locker code is 4242.\nAssistant: I've noted your locker code."
_HOME = "User: Remember my home phone is 0744 111 2222.\nAssistant: Noted your home phone."
_CARD = (
    "User: Remember that my card is 4111 1111 1111 4242.\nAssistant: I've noted your card "
    "number: 4111 1111 1111 4242."
)
_TELEFON = (
    "User: Ține minte că telefonul meu este 0721 555 4242.\nAssistant: Am notat telefonul tău, "
    "0721 555 4242."
)
_ASKED = "Forget the locker 4242 including the phone."
_SAID = "I've deleted those details from my memory."

SAYS_THE_WHOLE_REQUEST_WAS_FORGOTTEN = [
    _SAID,
    "I've removed that information from my memory.",
    "The requested information has been removed from my memory.",
    "I've removed those from my memory.",
    "Those details were deleted.",
    "Okay, I've forgotten that.",
    "I have now erased what you asked about.",
]
NAMES_A_ROW_OR_STATES_NO_REMOVAL = [
    "I've deleted those details from my memory, except the phone.",
    "I've deleted those details. Your phone number is still saved.",
    "I've removed the locker code. Those details are gone.",
    "I've removed that information, but your card stays.",
    "I've deleted 4242 from my memory.",
    "I'll delete those details.",
    "I couldn't delete those details.",
    "I haven't removed those details.",
    "Should I say those details were removed?",
    "Nothing was removed.",
    "If those details were removed, ask me again.",
    "I have processed your request.",
    "J'ai supprimé ces informations.",
]


@pytest.mark.parametrize("reply", SAYS_THE_WHOLE_REQUEST_WAS_FORGOTTEN)
def test_a_removal_naming_no_row_after_a_message_naming_a_kept_row_is_found(reply: str) -> None:
    assert unnamed_sentence(reply, (_CARD, _PHONE), (_LOCKER,), _ASKED) == reply


@pytest.mark.parametrize("reply", NAMES_A_ROW_OR_STATES_NO_REMOVAL)
def test_a_reply_naming_a_row_or_stating_no_removal_is_not_found(reply: str) -> None:
    assert unnamed_sentence(reply, (_CARD, _PHONE), (_LOCKER,), _ASKED) is None


@pytest.mark.parametrize(
    ("asked", "kept", "gone"),
    [
        ("Forget my locker code but keep the phone.", (_PHONE,), (_LOCKER,)),
        ("Forget the locker, keep the phone and the card.", (_CARD, _PHONE), (_LOCKER,)),
        ("Forget the locker 4242.", (_CARD, _PHONE), (_LOCKER,)),
        ("Forget my home phone.", (_PHONE,), (_HOME,)),
        ("Forget everything except the card.", (_CARD,), (_LOCKER, _PHONE)),
        ("Oublie le casier mais garde le téléphone.", (_PHONE,), (_LOCKER,)),
        ("Delete the locker code but leave the card number.", (_CARD,), (_LOCKER,)),
        ("Erase my locker code, I still need my card number.", (_CARD,), (_LOCKER,)),
        ("Please forget the locker code; the card number stays.", (_CARD,), (_LOCKER,)),
        ("Uită codul dulapului, mai puțin telefonul.", (_TELEFON,), (_LOCKER,)),
        ("Forget the locker code if the phone is gone.", (_PHONE,), (_LOCKER,)),
        ("Forget the locker code; if you delete the phone, tell me.", (_PHONE,), (_LOCKER,)),
        ("Forget the locker code, though I may forget the phone later.", (_PHONE,), (_LOCKER,)),
        ("", (_PHONE,), (_LOCKER,)),
    ],
)
def test_a_message_whose_forget_part_names_no_kept_row_marks_nothing(
    asked: str, kept: tuple[str, ...], gone: tuple[str, ...]
) -> None:
    assert unnamed_sentence(_SAID, kept, gone, asked) is None


def test_the_first_sentence_stating_the_removal_is_found() -> None:
    reply = "Done. I've removed those from my memory. Is there anything else?"
    assert unnamed_sentence(reply, (_PHONE,), (_LOCKER,), _ASKED) == (
        "I've removed those from my memory."
    )


def test_a_turn_that_deleted_nothing_marks_the_whole_request_claim() -> None:
    assert unnamed_sentence(_SAID, (_LOCKER, _PHONE), (), _ASKED) == _SAID


def _closed(reply: str, taint: TaintLedger, query: str = _ASKED) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    caps = TurnCapabilities(memory=recaller)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


def test_the_kept_note_names_a_whole_request_claim_in_place_of_its_plain_head() -> None:
    taint = TaintLedger(forget_kept=(_PHONE,), forget_gone=(_LOCKER,), forget_deleted=1)
    head = KEPT_CLAIM_NOTE.lstrip("\n").format(sentence=_SAID)
    assert _closed(_SAID, taint) == f"{_SAID}\n\n{head}\n- {_PHONE})"


def test_the_kept_note_keeps_its_plain_head_for_a_request_the_turn_completed() -> None:
    taint = TaintLedger(forget_kept=(_PHONE,), forget_gone=(_LOCKER,), forget_deleted=1)
    closed = _closed(_SAID, taint, query="Forget my locker code but keep the phone.")
    assert KEPT_NOTE.strip() in closed
    unknown = TaintLedger(forget_kept=(_PHONE,), forget_deleted=1)
    assert KEPT_NOTE.strip() in _closed(_SAID, unknown)
