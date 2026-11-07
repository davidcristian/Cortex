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
from cortex_core.numbers_left_claim import NUMBERS_LEFT_NOTE, names_still_held, says_forgotten
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
]

STILL_HELD = [
    "I've forgotten the exchange with your door code, but one other exchange still holds 1987.",
    "I deleted it, but the number is still stored in another exchange.",
    "I've forgotten your request, though I still remember the number.",
    "I removed one exchange; the number can still be recalled from another one.",
]

NOT_STILL_HELD = [
    "I've forgotten your door code.",
    "I've forgotten it, and no exchange still holds it.",
    "Is the number still stored?",
    "I've forgotten it, so nothing is still in my memory about it.",
]


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


def _closed(reply: str, *, left: bool) -> str:
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    parts = [reply]
    taint = TaintLedger(forget_asked=True, forget_calls=1, forget_numbers_left=left)
    runs = (ToolRun(name=FORGET_CHOSEN_TOOL_NAME, ok=True),)
    caps = TurnCapabilities(memory=recaller)
    list(limit_notes(StopLedger(), runs, parts, caps=caps, taint=taint, query="Forget it."))
    return "".join(parts)


@pytest.mark.parametrize("reply", FORGOTTEN)
def test_a_forgotten_claim_with_a_number_left_ends_with_the_note(reply: str) -> None:
    assert _closed(reply, left=True) == reply + NUMBERS_LEFT_NOTE
    assert _closed(reply, left=False) == reply


@pytest.mark.parametrize("reply", [*NOT_FORGOTTEN, *STILL_HELD])
def test_a_reply_that_claims_nothing_gone_or_names_the_row_gets_no_note(reply: str) -> None:
    assert _closed(reply, left=True) == reply


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
    events = [event async for event in engine.handle_turn("s", "Forget it.", turn_id="t-1")]
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


async def test_a_later_forget_of_the_number_itself_clears_the_note() -> None:
    rounds = [[_forget("door code")], [_forget("1987", 1)]]
    shown, left = await _turn((_DOOR, _ONLY_VALUE), rounds, "I've forgotten your door code.")
    assert NUMBERS_LEFT_NOTE not in shown
    assert left == []


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("blue Fiat", "I've forgotten that your car is a blue Fiat."),
        ("door code", "I've forgotten your door code, but 1987 is still held in another exchange."),
        ("door code", "OK."),
    ],
    ids=["no-number-deleted", "names-the-row", "no-claim"],
)
async def test_a_turn_with_no_number_left_or_a_reply_that_says_so_gets_no_note(
    asked: str, reply: str
) -> None:
    shown, _ = await _turn((_FIAT, _CODE, _DOOR, _ONLY_VALUE), [[_forget(asked)]], reply)
    assert NUMBERS_LEFT_NOTE not in shown


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
    reply = "I've forgotten your door code."
    shown, left = await _turn((_DOOR, _ONLY_VALUE, _FIAT), rounds, reply, answers)
    assert shown.endswith(reply + NUMBERS_LEFT_NOTE)
    assert "m1" in left


async def test_a_later_delete_of_the_rows_left_clears_the_note_after_an_unrelated_one() -> None:
    rounds = [[_forget("door code")], [_forget("blue Fiat", 1)], [_forget("1987", 2)]]
    reply = "I've forgotten your door code."
    shown, left = await _turn((_DOOR, _ONLY_VALUE, _FIAT), rounds, reply, (True, True, True))
    assert NUMBERS_LEFT_NOTE not in shown
    assert left == []
