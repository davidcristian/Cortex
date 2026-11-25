from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    GenerationBounds,
    InferenceEvent,
    InMemoryMemoryStore,
    JsonSchema,
    MemoryRecord,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)
from cortex_core.forget_open import Exchange
from cortex_core.forget_unsaid import FORGET_UNSAID_MSG, forget_unsaid, reads_call_words
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 25, 8, 0, 0, tzinfo=UTC)
_REX = "User: Merk dir, dass mein Hund Rex heißt.\nAssistant: Notiert."
_BELLO = "Merk dir, dass mein Hund Bello heißt."
_SORA = "Ține minte că sora mea vine mâine."
_CARD_GONE = "Merk dir, dass meine Karte weg muss."


def _forget(text: object, index: int = 0) -> ToolCall:
    return ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("Rex", _BELLO),
        ("Mein Hund heißt Rex.", _BELLO),
        ("sora mea vine vineri", _SORA),
        ("sora ta vine vineri", _SORA),
        ("Sora utilizatorului vine mâine.", _SORA),
        ("rouge", "Souviens-toi que mon vélo est bleu."),
        ("mon vélo est rouge", "Souviens-toi que mon vélo est bleu."),
        ("carnívoro", "Recuerda que soy vegetariano."),
        ("4111 1111 1111 4242", _CARD_GONE),
        ("my dog Bello", _BELLO),
    ],
)
def test_a_forget_naming_a_word_a_request_to_remember_lacks_is_unsaid(
    text: str, query: str
) -> None:
    assert forget_unsaid(_forget(text), query)


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("Bello", _BELLO),
        ("Mein Hund heißt Bello.", _BELLO),
        ("MEIN HUND HEISST BELLO", _BELLO),
        ("sora mea vine mâine", _SORA),
        ("cita a las 9", "Recuerda que tienes cita a las 9."),
        ("Karte", _CARD_GONE),
        ("meine Karte", _CARD_GONE),
        ("4242", "Merk dir, dass meine Karte 4242 weg muss."),
        ("", _BELLO),
    ],
)
def test_a_forget_naming_only_the_message_words_is_not_unsaid(text: str, query: str) -> None:
    assert not forget_unsaid(_forget(text), query)


@pytest.mark.parametrize("query", [_BELLO, _SORA, _CARD_GONE, "Recuerda que soy vegetariano."])
def test_a_request_to_remember_in_another_language_has_its_call_words_read(query: str) -> None:
    assert reads_call_words(query, ())
    assert not reads_call_words(query, [Exchange("", "I deleted your code.")])


@pytest.mark.parametrize(
    "query",
    [
        "Forget Rex.",
        "Remember that my dog is called Bello.",
        "Vergiss Rex.",
        "Mein Hund heißt Bello.",
    ],
)
def test_a_message_read_as_no_request_to_remember_in_another_language_has_no_words_read(
    query: str,
) -> None:
    assert not reads_call_words(query, ())


def test_another_tool_or_a_text_that_is_no_string_is_never_unsaid() -> None:
    other = ToolCall(id="x", name="schedule_task", arguments={"text": "Rex"})
    assert not forget_unsaid(other, _BELLO)
    assert not forget_unsaid(_forget(4242), _BELLO)


class _Clock:
    def now(self) -> datetime:
        return _AT


class _RoundsBackend:
    def __init__(self, rounds: Sequence[Sequence[ToolCall]]) -> None:
        self._rounds = list(rounds)
        self._step = 0

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
        step, self._step = self._step, self._step + 1
        if step >= len(self._rounds):
            yield TextChunk("done")
            return
        for call in self._rounds[step]:
            yield call


async def _loop(
    query: str, rounds: Sequence[Sequence[ToolCall]]
) -> tuple[list[str], RecordingAuditSink, RecordingConfirmer]:
    store = InMemoryMemoryStore()
    await store.add(MemoryRecord(id="rex", text=_REX, embedding=(1.0, 0.0), at=_AT))
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    audit, confirmer = RecordingAuditSink(), RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        audit,
        _Clock(),
        confirmer=confirmer,
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    context = ToolLoopContext(
        dispatcher=dispatcher,
        clock=_Clock(),
        turn_id="t",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        query=query,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    async for _ in stream_tool_loop(_RoundsBackend(rounds), "m", working, context):
        pass
    left = sorted(hit.record.id for hit in await store.search((1.0, 0.0), k=10))
    return left, audit, confirmer


async def test_every_unsaid_forget_of_the_old_name_is_refused_and_the_row_kept() -> None:
    left, audit, confirmer = await _loop(_BELLO, [[_forget("Rex")], [_forget("Rex", 1)]])
    assert left == ["rex"]
    assert not confirmer.requests
    assert [(record.ok, record.detail) for record in audit.records] == [
        (False, FORGET_UNSAID_MSG),
        (False, FORGET_UNSAID_MSG),
    ]


async def test_a_forget_naming_the_message_words_still_shows_its_card_and_runs() -> None:
    left, audit, _ = await _loop("Merk dir dass Rex weg muss.", [[_forget("Rex")]])
    assert left == []
    assert [record.ok for record in audit.records] == [True]


async def test_a_row_a_later_clause_names_in_a_role_no_reader_reads_is_kept() -> None:
    left, _, confirmer = await _loop("Merk dir, dass Rex weg muss.", [[_forget("Rex")]])
    assert (left, confirmer.requests) == (["rex"], ())
