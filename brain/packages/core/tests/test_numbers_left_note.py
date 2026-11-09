from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    UNFORGOTTEN_CLAIM_NOTE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    JsonSchema,
    MemoryRecaller,
    MemoryRecord,
    Message,
    RecordingAuditSink,
    SystemClock,
    TaintLedger,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.forget_count_note import forgot_count_note
from cortex_core.forget_unfound_claim import DECLINED_FORGET_NOTE
from cortex_core.numbers_left_claim import (
    NUMBERS_LEFT_NOTE,
    NUMBERS_LEFT_NOTES,
    names_still_held,
    says_forgotten,
)
from cortex_core.stops import StopLedger
from cortex_core.tools import ConfirmAnswer, ConfirmationRequest

_AT = datetime(2026, 11, 7, 8, 0, 0, tzinfo=UTC)
_DOOR = "User: Remember that my door code is 1987.\nAssistant: Noted, your door code is 1987."
_ONLY_VALUE = (
    "User: Which number did I give you for the front door? Reply with only the number."
    "\nAssistant: 1987"
)
_POOL = (
    "User: Souviens-toi que le code de mon casier à la piscine est 7731.\nAssistant: C'est noté."
)
_POOL_RECALL = "User: What is my swimming pool locker code?\nAssistant: Your locker code is 7731."
_TUER = "User: der Türcode ist 4512\nAssistant: Notiert."
_TUER_RESTATED = "User: Der Code 4512 am Hintereingang, oder?\nAssistant: Ja, der Türcode."
_FIAT = "User: Remember my car is a blue Fiat.\nAssistant: Noted."
_CODE = "User: My bike code is 4512.\nAssistant: Noted."

FORGOTTEN = [
    "OK. I've forgotten your door code.",
    "I've forgotten that.",
    "C'est fait, j'ai oublié le code de votre casier à la piscine.",
    "C'est fait, le code est supprimé.",
    "Ich habe deinen Türcode vergessen.",
    "Erledigt, der Code ist gelöscht.",
    "Listo, he olvidado tu código.",
    "Gata, am uitat codul ușii.",
    "Done, I removed your door code from my memory.",
    "Amintirea a fost ștearsă.",
    "Il a été supprimé.",
    "Sie wurde gelöscht.",
    "Am șters codul, dacă vrei să știi.",
    "Ich habe ihn gelöscht, wenn du willst, sag es mir.",
    "I deleted it, if you want to know.",
    "I deleted it and it will not come back.",
    "I'll confirm: I deleted it.",
    "It will not appear again, since I've deleted it.",
    "Es wurde gelöscht.",
    "Il a été supprimé, il ne sera plus rappelé.",
]

NOT_FORGOTTEN = [
    "Your door code is 1987.",
    "OK.",
    "I didn't forget anything.",
    "Should I forget your door code?",
    "Je n'ai rien oublié.",
    "Voulez-vous que le code soit supprimé ?",
    "Ich habe nichts gelöscht.",
    "No he olvidado nada.",
    "Nu am uitat nimic.",
    "Poate fi șters dacă vrei.",
    "Dacă vrei, poate fi șters.",
    "Peut être supprimé si tu veux.",
    "Si tu veux, il sera supprimé.",
    "Kann gelöscht werden, wenn du willst.",
    "Wenn du willst, wird es gelöscht.",
    "Puede ser borrado si quieres.",
    "Si quieres, puede ser eliminado.",
    "Ar putea fi șters.",
    "I can delete it if you want.",
    "If you like, it could be removed.",
    "I will delete it.",
    "I'll remove it from my memory.",
    "It will be deleted.",
    "I\u2019m going to delete it now.",
    "Il sera supprimé.",
    "Es wird gelöscht.",
    "Ich werde es löschen, es wird gelöscht.",
    "Será borrado.",
    "Va fi șters.",
]

STILL_HELD = [
    "I've forgotten the exchange with your door code, but one other exchange still holds 1987.",
    "I deleted it, but the number is still stored in another exchange.",
    "I've forgotten your request, though I still remember the number.",
    "I removed one exchange; the number can still be recalled from another one.",
    "I've forgotten your door code, though another exchange still mentions 1987.",
    "I've forgotten it, but the number still appears in one other memory.",
    "I've forgotten it, but if you check, the number still appears in one other memory.",
    "I've forgotten it, but one exchange still holds 1987, not the door code.",
    "I've forgotten it, but one exchange still holds 1987 if you want that gone too.",
    "I've forgotten it. Should you ask, I can say that one exchange still holds 1987.",
]

NOT_STILL_HELD = [
    "I've forgotten your door code.",
    "I've forgotten it, and no exchange still holds it.",
    "Is the number still stored?",
    "I've forgotten it, so nothing is still in my memory about it.",
    "I've forgotten it, and nothing still mentions it.",
    "I've forgotten it; no other exchange still appears in my memory with it.",
    "I've forgotten it, and it still appears that nothing else was stored.",
    "I've forgotten your door code. If it still appears in another chat, tell me.",
    "I've forgotten your door code. Should it still appear in a later chat, ask me again.",
    "I've forgotten your door code; it still appears in no other memory.",
    "I've forgotten your door code. If anything is still stored, tell me.",
    "I've forgotten your door code. Tell me whether it is still stored anywhere.",
    "I've forgotten your door code. Ask again in case it is still held somewhere.",
    "I've forgotten your door code. It is gone unless it is still stored elsewhere.",
    "I've forgotten your door code. The number is still stored nowhere.",
    "I've forgotten your door code. Another exchange still holds none of it.",
    "I've forgotten your door code. The number no longer appears in any memory.",
    "I've forgotten your door code. The number still appears nowhere.",
    "I've forgotten your door code, so nothing still mentions it.",
]


OTHER_HELD = [
    "I've forgotten your door code. The number 1987 also appears in another memory.",
    "J'ai oublié votre code, mais un autre souvenir contient encore 1987.",
    "Ich habe den Türcode vergessen, aber 4512 steht noch in einer anderen Erinnerung.",
    "I've forgotten it. One other memory holds 1987 too, so ask me to forget 1987 as well.",
    "He olvidado tu código, pero otro recuerdo todavía contiene 1987.",
    "Am uitat codul, dar o altă amintire încă conține 1987.",
    "I've forgotten your door code. Another memory that I saved on Monday holds 1987.",
]

OTHER_NOT_HELD = [
    "I've forgotten your door code. It also appears that nothing was stored.",
    "I've forgotten your door code. No other memory holds 1987.",
    "I've forgotten your door code. If another memory holds 1987, ask me to forget it too.",
    "I've forgotten your door code. Another memory that contains 1987 was deleted too.",
    "I've forgotten your door code. Does another memory hold 1987?",
    "I've forgotten your door code. Another memory holds your bike code.",
    "I've forgotten your door code, and the other memories have 1987 removed too.",
    "J'ai oublié votre code. Aucun autre souvenir ne contient 1987.",
    "Ich habe den Türcode vergessen. Kein anderer Eintrag enthält 4512.",
    "He olvidado tu código. Ningún otro recuerdo contiene 1987.",
    "Am uitat codul. Nicio altă amintire nu conține 1987.",
    "I've forgotten your door code. Your message mentions 1987.",
    "I've forgotten your door code. Another memory was from 2025.",
    "J'ai oublié votre code. Si un autre souvenir contient 1987, dites-le-moi.",
    "Ich habe den Türcode vergessen. Wenn eine andere Erinnerung 4512 enthält, sag es mir.",
    "Ich habe den Türcode vergessen. Falls eine andere Erinnerung 4512 enthält, sag es mir.",
    "Ich habe den Türcode vergessen und prüfe, ob eine andere Erinnerung 4512 enthält.",
    "Am uitat codul. Spune-mi dacă o altă amintire conține 1987.",
    "I've forgotten your door code. Another memory may hold 1987.",
    "Ich habe den Türcode vergessen. Eine andere Erinnerung kann 4512 enthalten.",
]

OTHER_NAMED = [
    "I forgot your PIN 4412. I checked the other memories that mention 4412, they are cleaned up.",
    "I forgot your PIN 4412. The other exchanges which contain 4412 are taken care of too.",
    "J'ai oublié votre code 4412, et les autres souvenirs qui contiennent 4412 ont disparu aussi.",
    "Ich habe den Türcode vergessen. Andere Einträge die 4512 enthalten sind verschwunden.",
    "He olvidado tu código. Los otros recuerdos que contienen 1987 desaparecieron.",
    "Am uitat codul. Alte amintiri care conțin 1987 au dispărut și ele.",
    "I've forgotten your door code. There is another memory that holds 1987.",
]


@pytest.mark.parametrize("reply", OTHER_NAMED)
def test_a_reply_naming_other_memories_by_what_they_hold_keeps_the_note(reply: str) -> None:
    assert not names_still_held(reply)
    assert _closed(reply, left=True) == reply + NUMBERS_LEFT_NOTE


@pytest.mark.parametrize("reply", OTHER_HELD)
def test_a_reply_naming_another_memory_holding_the_number_names_it_still_held(
    reply: str,
) -> None:
    assert names_still_held(reply)
    assert _closed(reply, left=True) == reply


@pytest.mark.parametrize("reply", OTHER_NOT_HELD)
def test_a_reply_not_stating_another_memory_holds_the_number_keeps_the_note(reply: str) -> None:
    assert not names_still_held(reply)
    assert _closed(reply, left=True) == reply + NUMBERS_LEFT_NOTE


@pytest.mark.parametrize("reply", FORGOTTEN)
def test_a_reply_saying_a_fact_went_says_forgotten(reply: str) -> None:
    assert says_forgotten(reply)


@pytest.mark.parametrize("reply", NOT_FORGOTTEN)
def test_a_reply_that_removes_nothing_does_not_say_forgotten(reply: str) -> None:
    assert not says_forgotten(reply)


@pytest.mark.parametrize("reply", STILL_HELD)
def test_a_reply_naming_the_row_left_names_it_still_held(reply: str) -> None:
    assert names_still_held(reply)


@pytest.mark.parametrize("reply", NOT_STILL_HELD)
def test_a_reply_naming_no_row_left_does_not_name_it_still_held(reply: str) -> None:
    assert not names_still_held(reply)


def _closed(reply: str, *, left: bool, query: str = "Forget it.") -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_numbers_left=left)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query=query))
    return "".join(parts)


@pytest.mark.parametrize(
    ("query", "language"),
    [
        ("Oublie mon code de porte.", "fr"),
        ("Vergiss meinen Türcode.", "de"),
        ("Olvida mi código de la puerta, por favor.", "es"),
        ("Uită codul meu de la ușă.", "ro"),
    ],
)
def test_a_numbers_left_note_is_written_in_the_language_of_the_message(
    query: str, language: str
) -> None:
    reply = "I've forgotten your door code."
    assert _closed(reply, left=True, query=query) == reply + NUMBERS_LEFT_NOTES[language]


@pytest.mark.parametrize("reply", FORGOTTEN)
def test_a_forgotten_claim_with_a_number_left_ends_with_the_note(reply: str) -> None:
    assert _closed(reply, left=True) == reply + NUMBERS_LEFT_NOTE
    assert _closed(reply, left=False) == reply


@pytest.mark.parametrize("reply", [*NOT_FORGOTTEN, *STILL_HELD])
def test_a_reply_that_claims_nothing_gone_or_names_the_row_gets_no_note(reply: str) -> None:
    assert _closed(reply, left=True) == reply


@pytest.mark.parametrize("reply", NOT_STILL_HELD[-12:])
def test_a_forgotten_claim_naming_the_row_only_in_a_condition_or_negation_gets_the_note(
    reply: str,
) -> None:
    assert _closed(reply, left=True) == reply + NUMBERS_LEFT_NOTE


class _Rounds:
    def __init__(self, rounds: Sequence[Sequence[ToolCall]], reply: str) -> None:
        self._rounds = list(rounds)
        self._reply = reply

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        if not self._rounds:
            yield TextChunk(self._reply)
            return
        for call in self._rounds.pop(0):
            yield call


class _Answers:
    def __init__(self, answers: Sequence[bool]) -> None:
        self._answers = list(answers)

    async def confirm(self, request: ConfirmationRequest) -> ConfirmAnswer:
        del request
        return ConfirmAnswer.APPROVED if self._answers.pop(0) else ConfirmAnswer.DECLINED


class _Clock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(minutes=10, seconds=self._ticks)


def _forget(text: str, index: int = 0) -> ToolCall:
    return ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _turn(
    texts: Sequence[str],
    rounds: Sequence[Sequence[ToolCall]],
    reply: str,
    answers: Sequence[bool] = (True, True),
    query: str = "Forget it.",
) -> tuple[str, list[str]]:
    store, embedder = InMemoryMemoryStore(), HashEmbedder()
    for index, text in enumerate(texts):
        embedding = tuple(await embedder.embed(text))
        at = _AT + timedelta(minutes=index)
        await store.add(MemoryRecord(id=f"m{index}", text=text, embedding=embedding, at=at))
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _Clock(),
        confirmer=_Answers(answers),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    caps = TurnCapabilities(memory=MemoryRecaller(store, embedder, SystemClock()), tools=dispatcher)
    engine = TurnEngine(InMemorySessionStore(), _Rounds(rounds, reply), _Clock(), capabilities=caps)
    events = [event async for event in engine.handle_turn("s", query, turn_id="t-1")]
    left = sorted(hit.record.id for hit in await store.search(await embedder.embed("x"), k=100))
    return "".join(event.text for event in events if isinstance(event, TextDelta)), left


@pytest.mark.parametrize(
    ("texts", "asked", "reply"),
    [
        ((_DOOR, _ONLY_VALUE), "door code", "I've forgotten that."),
        ((_POOL, _POOL_RECALL), "casier à la piscine", "C'est fait, j'ai oublié le code."),
        ((_TUER, _TUER_RESTATED), "Türcode ist", "Ich habe den Türcode vergessen."),
    ],
    ids=["value-only-recall", "french-text-english-recall", "german-am"],
)
async def test_a_forget_leaving_a_number_closes_the_claim_with_the_note(
    texts: tuple[str, str], asked: str, reply: str
) -> None:
    shown, left = await _turn(texts, [[_forget(asked)]], reply)
    assert shown.endswith(reply + NUMBERS_LEFT_NOTE)
    assert UNFORGOTTEN_CLAIM_NOTE not in shown
    assert left == ["m1"]


async def test_a_later_forget_of_the_number_the_message_names_clears_the_note() -> None:
    rounds = [[_forget("door code")], [_forget("1987", 1)]]
    reply, query = "I've forgotten your door code.", "Forget my door code and 1987 too."
    shown, left = await _turn((_DOOR, _ONLY_VALUE), rounds, reply, query=query)
    assert NUMBERS_LEFT_NOTE not in shown
    assert left == []


async def test_a_later_forget_of_a_number_the_message_lacks_keeps_its_rows_and_the_note() -> None:
    rounds = [[_forget("door code")], [_forget("1987", 1)]]
    shown, left = await _turn((_DOOR, _ONLY_VALUE), rounds, "I've forgotten your door code.")
    assert shown.endswith(NUMBERS_LEFT_NOTE)
    assert left == ["m1"]


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("blue Fiat", "I've forgotten that your car is a blue Fiat."),
        ("door code", "I've forgotten your door code, but 1987 is still held in another exchange."),
    ],
    ids=["no-number-deleted", "names-the-row"],
)
async def test_a_turn_with_no_number_left_or_a_reply_that_says_so_gets_no_note(
    asked: str, reply: str
) -> None:
    shown, _ = await _turn((_FIAT, _CODE, _DOOR, _ONLY_VALUE), [[_forget(asked)]], reply)
    assert NUMBERS_LEFT_NOTE not in shown


async def test_a_reply_naming_no_removal_gets_the_count_note_then_the_numbers_left_note() -> None:
    shown, _ = await _turn((_FIAT, _CODE, _DOOR, _ONLY_VALUE), [[_forget("door code")]], "OK.")
    assert shown == "OK." + forgot_count_note(1, "en") + NUMBERS_LEFT_NOTE


@pytest.mark.parametrize(
    ("rounds", "answers"),
    [
        ([[_forget("door code")], [_forget("blue Fiat", 1)]], (True, True)),
        ([[_forget("door code"), _forget("blue Fiat", 1)]], (True, True)),
        ([[_forget("blue Fiat")], [_forget("door code", 1)]], (True, True)),
        ([[_forget("door code")], [_forget("1987", 1)]], (True, False)),
        ([[_forget("door code")], [_forget("dentist", 1)]], (True,)),
        ([[_forget("1987")], [_forget("door code", 1)]], (False, True)),
    ],
    ids=[
        "unrelated-delete-after",
        "unrelated-delete-same-round",
        "unrelated-delete-before",
        "denied-forget-of-the-number",
        "later-forget-matching-nothing",
        "denied-forget-before",
    ],
)
async def test_a_number_left_by_any_delete_of_the_turn_keeps_the_note(
    rounds: list[list[ToolCall]], answers: tuple[bool, ...]
) -> None:
    reply, query = "I've forgotten your door code.", "Forget my door code and 1987."
    shown, left = await _turn((_DOOR, _ONLY_VALUE, _FIAT), rounds, reply, answers, query)
    declined = DECLINED_FORGET_NOTE if False in answers else ""
    assert shown.endswith(reply + NUMBERS_LEFT_NOTE + declined)
    assert "m1" in left


async def test_a_later_delete_of_the_rows_left_clears_the_note_after_an_unrelated_one() -> None:
    rounds = [[_forget("door code")], [_forget("blue Fiat", 1)], [_forget("1987", 2)]]
    reply = "I've forgotten your door code."
    query = "Forget my door code, the Fiat and 1987."
    shown, left = await _turn((_DOOR, _ONLY_VALUE, _FIAT), rounds, reply, (True, True, True), query)
    assert NUMBERS_LEFT_NOTE not in shown
    assert left == []


async def test_a_forget_reply_keeping_the_row_the_message_asked_to_keep_gets_no_note() -> None:
    bike = "User: Remember that my bike lock code is 7319.\nAssistant: Noted."
    shed = "User: Remember that the shed padlock code is also 7319.\nAssistant: Noted."
    reply = "Done, I've forgotten your bike lock code and kept the shed one."
    query = "Forget my bike lock code 7319, keep the shed one."
    shown, left = await _turn((bike, shed), [[_forget("7319")]], reply, query=query)
    assert (shown, left) == (reply, ["m1"])
