from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    ForgetChosenTool,
    InMemoryMemoryStore,
    MemoryRecord,
    ToolCall,
)
from cortex_core.memory_claim import names_spared, unkept_note_due
from cortex_core.memory_claim_other import names_spared_other
from cortex_core.tools import TurnStamp

_AT = datetime(2026, 11, 10, 5, 0, 0, tzinfo=UTC)
_OWN = "User: Remember that my phone number is 0151 2345 6789.\nAssistant: Noted."
_ANNA = "User: Remember that Anna's phone is 015 123 456 999.\nAssistant: Noted."
_ANNABEL = "User: Remember that Annabel's phone is 0170 555 1234.\nAssistant: Noted."
_ANNA_ROW = ("User: Remember that Anna's phone is 015 123 456 999. Assistant: Noted.",)
_KEEP_ANNA = "Forget my phone number but keep Anna's phone."
_ES = ("User: Recuerda que mi código del gimnasio es 5521. Assistant: Anotado.",)
_RO = ("User: Ține minte codul de la sală 5521. Assistant: Notat.",)
_FR = ("User: Souviens-toi que le code de mon casier est 4417. Assistant: C'est noté.",)
_DE = ("User: Merk dir meinen Fahrradcode 7319. Assistant: Notiert.",)
_EN = ("User: Remember my gym code 5521. Assistant: Noted.",)

KEEPS_A_STORED_ROW = [
    ("He borrado tu PIN del banco y he guardado tu código del gimnasio.", _ES),
    ("He borrado tu PIN del banco; tu código del gimnasio queda guardado.", _ES),
    ("Am șters PIN-ul de la bancă și am salvat codul de la sală.", _RO),
    ("J'ai effacé votre code bancaire et j'ai enregistré votre code de casier.", _FR),
    ("Ich habe den Bankcode gelöscht, aber dein Fahrradcode ist gespeichert.", _DE),
    ("He borrado tu PIN del banco y he guardado tu código del gimnasio 5521.", _ES),
    ("J'ai effacé votre code bancaire et j'ai enregistré votre code de casier 44 17.", _FR),
]
CLAIMS_A_NEW_FACT = [
    ("He borrado tu PIN del banco y he guardado tu nuevo código del gimnasio.", _ES),
    ("He borrado tu PIN del banco y he anotado tu código del gimnasio.", _ES),
    ("Guardado. He borrado tu PIN del banco y he guardado tu código del gimnasio.", _ES),
    ("He guardado tu código del gimnasio. También he anotado que te gusta el té.", _ES),
    ("He borrado tu PIN del banco y he guardado tu código del gimnasio.", _EN),
    ("Am șters PIN-ul și am salvat noul cod de la sală.", _RO),
    ("He borrado tu PIN del banco y he guardado tu código del gimnasio.", ()),
    ("He borrado tu PIN del banco y he guardado tu código del gimnasio 7788.", _ES),
    ("J'ai effacé votre code bancaire et j'ai enregistré votre code de casier 4418.", _FR),
]


@pytest.mark.parametrize(("reply", "spared"), KEEPS_A_STORED_ROW)
def test_a_reply_in_another_language_keeping_a_stored_row_gets_no_note(
    reply: str, spared: tuple[str, ...]
) -> None:
    assert names_spared_other(reply, spared)
    assert not unkept_note_due("Olvida mi PIN.", reply, spared, forget_called=True)
    assert unkept_note_due("Olvida mi PIN.", reply, (), forget_called=True)


@pytest.mark.parametrize(("reply", "spared"), CLAIMS_A_NEW_FACT)
def test_a_reply_in_another_language_claiming_more_keeps_the_note(
    reply: str, spared: tuple[str, ...]
) -> None:
    assert not names_spared_other(reply, spared)
    assert unkept_note_due("Olvida mi PIN.", reply, spared, forget_called=True)


@pytest.mark.parametrize(
    "reply",
    [
        "¿Quieres que guarde tu código del gimnasio?",
        "Si quieres, puedo guardar tu código del gimnasio.",
        "No he guardado tu código del gimnasio.",
    ],
)
def test_a_question_condition_or_negation_in_another_language_claims_nothing(reply: str) -> None:
    assert not unkept_note_due("Olvida mi PIN.", reply, (), forget_called=True)


def test_a_keep_claim_naming_more_than_a_stored_row_keeps_the_note() -> None:
    assert names_spared("OK. I've forgotten your phone number and kept Anna's.", _ANNA_ROW)
    assert not names_spared("I've forgotten your number and kept your new phone.", _ANNA_ROW)
    assert not names_spared("I've forgotten your number and kept Anna's new phone.", _ANNA_ROW)


def test_a_keep_claim_naming_a_number_no_stored_row_holds_keeps_the_note() -> None:
    held = "I've forgotten your phone number and kept Anna's phone 015 123 456 999 in memory."
    assert names_spared(held, _ANNA_ROW)
    assert names_spared(held.replace("015 123 456 999", "015123456999"), _ANNA_ROW)
    assert not names_spared(held.replace("999", "998"), _ANNA_ROW)
    assert unkept_note_due(_KEEP_ANNA, held.replace("999", "998"), _ANNA_ROW, forget_called=True)


def _row(record_id: str, text: str, minutes: int) -> MemoryRecord:
    at = _AT + timedelta(minutes=minutes)
    return MemoryRecord(id=record_id, text=text, embedding=(1.0, 0.0), at=at)


async def _spared(query: str) -> tuple[str, ...] | None:
    store = InMemoryMemoryStore()
    for number, (record_id, text) in enumerate(
        (("own", _OWN), ("anna", _ANNA), ("annabel", _ANNABEL))
    ):
        await store.add(_row(record_id, text, number))
    tool = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    stamp = TurnStamp(session_id="chat-k", turn_id="t1", query=query)
    arguments = {"text": "my phone number"}
    call = ToolCall(id="c1", name=FORGET_CHOSEN_TOOL_NAME, arguments=arguments, stamp=stamp)
    assert await tool.card(call) is not None
    return (await tool.invoke(call)).spared


async def test_a_forget_reports_a_row_its_keep_clause_names_that_no_call_matched() -> None:
    spared = await _spared(_KEEP_ANNA)
    assert spared == _ANNA_ROW
    reply = "OK. I've forgotten your phone number and kept Anna's."
    assert not unkept_note_due(_KEEP_ANNA, reply, spared or (), forget_called=True)


async def test_a_forget_with_no_keep_clause_reports_no_unmatched_row() -> None:
    assert await _spared("Forget my phone number.") == ()
