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
    "I'll remember it until the end of our conversation.",
    "I'll keep it in mind while this chat lasts.",
    "I'll remember it as long as this conversation lasts.",
    "I've noted that your seat on the train is 14C. I'll keep that in mind as we continue our "
    "conversation!",
    "I'll remember it as we go on with this chat.",
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
    "I'll remember it until the end of the year.",
    "I'll keep it in mind while you travel.",
    "I'll remember it as long as you like, in this chat and later ones.",
    "Noted. We can continue our conversation whenever you like.",
    "I'll keep that in mind as we continue to plan your trip.",
    "As we continue our conversation, tell me if anything changes.",
    "I'll keep it in mind as we continue our conversations in the future.",
]


CHAT_ONLY_OTHER = [
    "C'est bien noté. Je m'en souviendrai pour la suite de notre conversation.",
    "C'est noté, j'ai retenu que votre code est 4512. Je m'en souviendrai pour la suite de notre "
    "conversation !",
    "Je le garde en tête pendant cette conversation.",
    "Pendant cette conversation, je m'en souviendrai.",
    "J'ai noté votre code pour la durée de cet échange.",
    "Ich merke es mir für den Rest unseres Gesprächs.",
    "Ich habe es in diesem Gespräch notiert.",
    "Für die Dauer dieses Chats behalte ich das im Kopf.",
    "Lo recordaré durante esta conversación.",
    "Lo tendré en cuenta durante el resto de nuestra charla.",
    "He anotado tu código para esta sesión.",
    "Voi reține asta pe parcursul conversației.",
    "Am notat codul pentru restul conversației noastre.",
    "O să țin minte în această conversație.",
    "Voi reţine asta pe parcursul conversaţiei.",
    "Ich merke es mir für den Rest unseres Gesprächs, alles klar.",
    "Ich merke es mir in diesem Gespräch, Sie können es jederzeit ändern.",
    "Je garde votre code pendant cette conversation, et chaque détail compte.",
    "Lo recordaré mientras dure esta conversación.",
    "Je m'en souviendrai jusqu'à la fin de notre échange.",
    "Je m\u2019en souviendrai jusqu\u2019à la fin de cette conversation.",
    "Je m'en souviendrai tant que dure notre conversation.",
    "Ich merke es mir, solange dieses Gespräch dauert.",
    "Voi reține asta până la sfârșitul conversației.",
    "Je m'en souviendrai pendant le chat.",
    "J'ai noté votre code pour ce chat.",
]

NOT_CHAT_ONLY_OTHER = [
    "Merci pour cette conversation.",
    "Je suis ravi de vous aider pendant cette conversation.",
    "Dans cette conversation, vous m'avez demandé l'heure.",
    "Je m'en souviendrai pour nos prochaines conversations.",
    "Je m'en souviendrai, pas seulement pendant cette conversation.",
    "Voulez-vous que je m'en souvienne pendant cette conversation ?",
    "C'est noté.",
    "Danke für dieses Gespräch.",
    "In diesem Gespräch haben Sie nach der Uhrzeit gefragt.",
    "Ich merke es mir auch für künftige Gespräche.",
    "Ich merke es mir nicht nur für dieses Gespräch.",
    "Gracias por esta conversación.",
    "En esta conversación me preguntaste la hora.",
    "Lo recordaré también en futuras conversaciones.",
    "¿Quieres que lo recuerde durante esta conversación?",
    "Mulțumesc pentru această conversație.",
    "În această conversație m-ați întrebat ora.",
    "Voi reține asta și în conversațiile viitoare.",
    "Voi reține asta, nu doar pe parcursul conversației.",
    "Je m'en souviendrai pendant cette conversation et dans chaque nouvelle conversation.",
    "Ich merke es mir in diesem Gespräch und in jedem anderen Gespräch.",
    "Lo recordaré en esta conversación y en otras conversaciones.",
    "Voi reține asta în această conversație și în toate conversațiile.",
    "J'ai noté d'acheter des croquettes pour le chat.",
    "Lo recordaré mientras dure el viaje.",
    "Je m'en souviendrai jusqu'à la fin de l'année.",
    "Ich merke es mir, solange die Reise dauert.",
    "Voi reține asta până la sfârșitul anului.",
    "Lo recordaré mientras dure esta conversación y en las próximas.",
]


@pytest.mark.parametrize("reply", CHAT_ONLY + CHAT_ONLY_OTHER)
def test_a_reply_keeping_the_fact_for_this_chat_claims_chat_only(reply: str) -> None:
    assert claims_chat_only(reply)


@pytest.mark.parametrize("reply", NOT_CHAT_ONLY + NOT_CHAT_ONLY_OTHER)
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
