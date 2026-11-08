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
from cortex_core.forget_value_unasked import FORGET_VALUE_MSG, value_unasked
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 8, 8, 0, 0, tzinfo=UTC)
_GYM = "User: Remember that my gym locker number is 5521.\nAssistant: Noted."
_SHED = "User: Remember that the shed padlock code is also 5521.\nAssistant: Noted."
_ASKED = "Forget my gym locker number."


def _forget(text: str, index: int = 0) -> ToolCall:
    return ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("5521", _ASKED),
        ("55-21", _ASKED),
        ("5521", "Oublie le numéro de mon casier."),
        ("1987", "Forget my door code."),
        ("B7731X", "Vergiss meinen Spindcode."),
    ],
)
def test_a_value_the_message_lacks_is_unasked_after_a_delete_left_it(text: str, query: str) -> None:
    assert value_unasked(_forget(text), query, left=True)
    assert not value_unasked(_forget(text), query, left=False)


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("5521", "Forget 5521."),
        ("5521", "Forget the number 5521 everywhere."),
        ("5521", "Forget my gym locker number, it is 55 21."),
        ("5521", "Oublie le 5521 partout."),
        ("5521", "Vergiss die Nummer 5521 überall."),
        ("5521", "Olvida el número 5521 en todas partes."),
        ("5521", "Uită numărul 5521 peste tot."),
        ("7731", "Forget B7731X."),
        ("B7731X", "Forget 7731."),
        ("1987", "Forget the code 1987."),
        ("015123456789", "Forget 0151 2345 6789."),
        ("padlock", _ASKED),
        ("gym locker 55", _ASKED),
    ],
)
def test_a_value_the_message_holds_or_a_text_with_no_value_is_asked(text: str, query: str) -> None:
    assert not value_unasked(_forget(text), query, left=True)


def test_another_tool_or_a_missing_text_is_never_unasked() -> None:
    other = ToolCall(id="x", name="schedule_task", arguments={"text": "5521"})
    missing = ToolCall(id="y", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": 5521})
    assert not value_unasked(other, _ASKED, left=True)
    assert not value_unasked(missing, _ASKED, left=True)


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
    for record_id, text in (("gym", _GYM), ("shed", _SHED)):
        await store.add(MemoryRecord(id=record_id, text=text, embedding=(1.0, 0.0), at=_AT))
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


async def test_an_unasked_value_forget_after_the_delete_keeps_the_other_fact() -> None:
    rounds = [[_forget("gym locker number")], [_forget("5521", 1)]]
    left, audit, confirmer = await _loop(_ASKED, rounds)
    assert left == ["shed"]
    assert len(confirmer.requests) == 1
    assert [(record.ok, record.detail) for record in audit.records][1] == (False, FORGET_VALUE_MSG)


async def test_a_retry_of_the_value_runs_its_card_once_refused() -> None:
    rounds = [[_forget("gym locker number")], [_forget("5521", 1)], [_forget("5521", 2)]]
    left, _, confirmer = await _loop(_ASKED, rounds)
    assert left == []
    assert len(confirmer.requests) == 2


@pytest.mark.parametrize(
    "query", ["Forget my gym locker number and 5521 everywhere.", "Oublie mon casier et 5521."]
)
async def test_a_value_forget_the_message_names_runs_after_the_delete(query: str) -> None:
    left, audit, _ = await _loop(query, [[_forget("gym locker number")], [_forget("5521", 1)]])
    assert left == []
    assert [record.ok for record in audit.records] == [True, True]
