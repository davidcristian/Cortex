from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from cortex_core import (
    DENIED_MSG,
    EXPIRED_MSG,
    UNANSWERED_MSG,
    USER_DECLINED_MSG,
    DispatchPolicy,
    DispatchRefusal,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    ResultNote,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolSpec,
    TurnStamp,
)

_AT = datetime(2026, 10, 29, 2, 0, 0, tzinfo=UTC)
_NOTE = "Nothing in this message is kept."


class _Clock:
    def now(self) -> datetime:
        return _AT


class _Noted:
    @property
    def result_note(self) -> str:
        return _NOTE


async def _forgot(arguments: Mapping[str, object]) -> str:
    del arguments
    return "forgot 1."


async def _broke(arguments: Mapping[str, object]) -> str:
    del arguments
    msg = "the store broke."
    raise ToolError(msg)


def _dispatcher(
    sink: RecordingAuditSink, confirmer: RecordingConfirmer | None = None
) -> ToolDispatcher:
    registry = InMemoryToolRegistry(
        {
            "forget": (ToolSpec("forget", "forget", {}, confirm_required=True), _forgot),
            "broken": (ToolSpec("broken", "broken", {}), _broke),
            "plain": (ToolSpec("plain", "plain", {}), _forgot),
        }
    )
    policy = DispatchPolicy(
        confirm_names={"forget"}, notes={"forget": _Noted(), "broken": _Noted()}
    )
    return ToolDispatcher(registry, sink, _Clock(), confirmer=confirmer, policy=policy)


def _call(name: str = "forget") -> ToolCall:
    return ToolCall(id="c1", name=name, arguments={"text": "4242"})


def test_a_built_in_with_a_result_note_is_seen_as_one() -> None:
    assert isinstance(_Noted(), ResultNote)


async def test_an_approved_call_that_ran_ends_with_the_note() -> None:
    result = await _dispatcher(RecordingAuditSink(), RecordingConfirmer(answer=True)).dispatch(
        _call()
    )
    assert result.content == f"forgot 1. {_NOTE}"


async def test_a_call_the_person_declined_ends_with_the_note() -> None:
    result = await _dispatcher(RecordingAuditSink(), RecordingConfirmer(answer=False)).dispatch(
        _call()
    )
    assert result.content == f"{USER_DECLINED_MSG} {_NOTE}"


async def test_a_card_that_expired_ends_with_the_note() -> None:
    confirmer = RecordingConfirmer(answer=True)
    confirmer.answer_nothing()
    result = await _dispatcher(RecordingAuditSink(), confirmer).dispatch(_call())
    assert result.content == f"{EXPIRED_MSG} {_NOTE}"


async def test_a_card_nobody_can_answer_ends_with_the_note() -> None:
    result = await _dispatcher(RecordingAuditSink()).dispatch(_call())
    assert result.content == f"{UNANSWERED_MSG} {_NOTE}"


@pytest.mark.parametrize(
    "refusal", [refusal for refusal in DispatchRefusal if refusal is not DispatchRefusal.UNASKED]
)
async def test_a_call_refused_before_it_ran_ends_with_the_note(refusal: DispatchRefusal) -> None:
    result = await _dispatcher(RecordingAuditSink()).dispatch(_call(), refusal=refusal)
    assert result.content == f"{refusal.message} {_NOTE}"


async def test_a_call_refused_as_unasked_has_no_note_since_its_turn_is_kept() -> None:
    refusal = DispatchRefusal.UNASKED
    result = await _dispatcher(RecordingAuditSink()).dispatch(_call(), refusal=refusal)
    assert result.content == refusal.message


async def test_a_call_blocked_on_a_tainted_turn_ends_with_the_note() -> None:
    result = await _dispatcher(RecordingAuditSink(), RecordingConfirmer(answer=True)).dispatch(
        _call(), stamp=TurnStamp(tainted=True)
    )
    assert result.content == f"{DENIED_MSG} {_NOTE}"


async def test_a_tool_that_failed_ends_with_the_note() -> None:
    result = await _dispatcher(RecordingAuditSink()).dispatch(_call("broken"))
    assert (result.content, result.is_error) == (f"the store broke. {_NOTE}", True)


async def test_a_tool_with_no_note_keeps_its_result_as_it_is() -> None:
    result = await _dispatcher(RecordingAuditSink()).dispatch(_call("plain"))
    assert result.content == "forgot 1."


async def test_the_audit_line_records_the_outcome_without_the_note() -> None:
    sink = RecordingAuditSink()
    await _dispatcher(sink, RecordingConfirmer(answer=False)).dispatch(_call())
    assert [record.detail for record in sink.records] == [USER_DECLINED_MSG]
