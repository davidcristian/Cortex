from collections.abc import Sequence

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    UNKEPT_CLAIM_NOTE,
    HashEmbedder,
    InMemoryMemoryStore,
    MemoryRecaller,
    SessionMemoryScope,
    SystemClock,
    TaintLedger,
    ToolRun,
    TurnCapabilities,
)
from cortex_core.chat_only_claim import KEPT_BEYOND_CHAT_NOTE, claims_chat_only
from cortex_core.closing_notes import limit_notes
from cortex_core.scope import MemoryScope
from cortex_core.stops import StopLedger

_ASK = "Please remember this: my daughter is allergic to peanuts."
_CHAT_ONLY = (
    "I've noted that your daughter is allergic to peanuts. I will keep this in mind for our "
    "conversation."
)

CHAT_ONLY = [
    _CHAT_ONLY,
    "I've noted that your car is a blue Fiat. I'll keep that in mind for our conversation!",
    "Got it, I'll remember that during this chat.",
    "I'll keep track of it for the rest of this session.",
    "Noted.\nI will hold on to that throughout our current conversation.",
    "I\u2019ll remember it in this conversation.",
    "I'll keep that in mind for our conversation. Anything else I can help with?",
    "I'll keep this in mind for our chat. Tell me later if it changes.",
]

NOT_CHAT_ONLY = [
    "OK. I've noted that your dentist appointment is on the 14th.",
    "Got it. I'll remember that your wifi password is on the router label.",
    "I will keep this in mind for our future conversations.",
    "I'll remember it, not just for this chat.",
    "I'll keep it in mind in this chat and in later ones.",
    "I will remember it beyond this conversation.",
    "Do you want me to keep this in mind for our conversation?",
    "In this conversation you told me your car is a Fiat, and I noted it.",
    "Your gym class is on Tuesday, as you said in this chat.",
    "I'll save the file in the folder for this session's notes.",
]


@pytest.mark.parametrize("reply", CHAT_ONLY)
def test_a_reply_keeping_the_fact_for_this_chat_claims_chat_only(reply: str) -> None:
    assert claims_chat_only(reply)


@pytest.mark.parametrize("reply", NOT_CHAT_ONLY)
def test_a_reply_without_a_chat_limit_does_not_claim_chat_only(reply: str) -> None:
    assert not claims_chat_only(reply)


class _SharedScope:
    def write_scope(self, session_id: str) -> str:
        del session_id
        return "household"

    def read_scopes(self, session_id: str) -> tuple[str, ...]:
        del session_id
        return ("household",)


def _shown(
    reply: str,
    *,
    taint: TaintLedger,
    runs: Sequence[ToolRun] = (),
    memory: bool = True,
    scope: MemoryScope = GLOBAL_MEMORY_SCOPE,
) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock(), scope=scope)
    caps = TurnCapabilities(memory=recaller if memory else None)
    parts = [reply]
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=_ASK))
    return "".join(parts)


def test_a_stored_turn_whose_reply_keeps_the_fact_for_this_chat_ends_with_the_note() -> None:
    assert _shown(_CHAT_ONLY, taint=TaintLedger()) == _CHAT_ONLY + KEPT_BEYOND_CHAT_NOTE


def test_a_stored_turn_whose_reply_names_no_chat_limit_has_no_note() -> None:
    reply = "I've noted that your daughter is allergic to peanuts."
    assert _shown(reply, taint=TaintLedger()) == reply


def test_a_turn_with_memory_off_has_no_note() -> None:
    assert _shown(_CHAT_ONLY, taint=TaintLedger(), memory=False) == _CHAT_ONLY


def test_a_turn_memory_does_not_store_shows_the_unkept_note_alone() -> None:
    taint = TaintLedger(forget_asked=True, forget_calls=1)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    assert _shown(_CHAT_ONLY, taint=taint, runs=runs) == _CHAT_ONLY + UNKEPT_CLAIM_NOTE


def test_a_turn_stored_for_this_chat_alone_has_no_note() -> None:
    assert _shown(_CHAT_ONLY, taint=TaintLedger(), scope=SessionMemoryScope()) == _CHAT_ONLY


def test_a_scope_every_chat_shares_ends_with_the_note() -> None:
    shown = _shown(_CHAT_ONLY, taint=TaintLedger(), scope=_SharedScope())
    assert shown == _CHAT_ONLY + KEPT_BEYOND_CHAT_NOTE
