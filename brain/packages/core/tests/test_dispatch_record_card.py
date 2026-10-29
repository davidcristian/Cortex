from collections.abc import Mapping
from datetime import UTC, datetime

from cortex_core import (
    DENIED_MSG,
    UNANSWERED_MSG,
    DispatchPolicy,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnStamp,
)


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _Card:
    async def card(self, call: ToolCall) -> str | None:
        record = call.arguments["id"]
        return None if record == "gone" else f"record behind {record}"


async def _ran(arguments: Mapping[str, object]) -> str:
    return f"ran:{arguments['id']}"


def _dispatcher(confirmer: RecordingConfirmer | None) -> ToolDispatcher:
    spec = {
        name: (ToolSpec(name=name, description=name, parameters={}), _ran)
        for name in ("drop", "send")
    }
    return ToolDispatcher(
        InMemoryToolRegistry(spec),
        RecordingAuditSink(),
        _Clock(),
        confirmer=confirmer,
        policy=DispatchPolicy(
            confirm_names={"drop", "send"},
            confirm_reasons={"drop": "a configured reason"},
            record_cards={"drop": _Card()},
        ),
    )


async def test_a_record_card_is_shown_on_a_tainted_turn_with_the_record_as_its_reason() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _dispatcher(confirmer).dispatch(
        ToolCall(id="c", name="drop", arguments={"id": "r-1"}), stamp=TurnStamp(tainted=True)
    )
    assert result.content == "ran:r-1"
    (request,) = confirmer.requests
    assert (request.tool_name, request.reason) == ("drop", "record behind r-1")


async def test_a_record_card_replaces_the_configured_reason_on_a_clean_turn() -> None:
    confirmer = RecordingConfirmer(answer=True)
    await _dispatcher(confirmer).dispatch(ToolCall(id="c", name="drop", arguments={"id": "r-2"}))
    (request,) = confirmer.requests
    assert request.reason == "record behind r-2"


async def test_a_record_card_for_one_tool_leaves_another_blocked_on_a_tainted_turn() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _dispatcher(confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"id": "r-3"}), stamp=TurnStamp(tainted=True)
    )
    assert result.content == DENIED_MSG
    assert confirmer.requests == ()


async def test_a_record_card_with_no_confirmer_is_unanswered_and_does_not_run() -> None:
    result = await _dispatcher(None).dispatch(
        ToolCall(id="c", name="drop", arguments={"id": "r-4"}), stamp=TurnStamp(tainted=True)
    )
    assert result.content == UNANSWERED_MSG


async def test_a_record_card_with_nothing_to_ask_runs_the_call_without_asking() -> None:
    confirmer = RecordingConfirmer(answer=False)
    result = await _dispatcher(confirmer).dispatch(
        ToolCall(id="c", name="drop", arguments={"id": "gone"}), stamp=TurnStamp(tainted=True)
    )
    assert result.content == "ran:gone"
    assert confirmer.requests == ()


async def test_a_record_card_with_nothing_to_ask_runs_with_no_confirmer() -> None:
    result = await _dispatcher(None).dispatch(
        ToolCall(id="c", name="drop", arguments={"id": "gone"})
    )
    assert result.content == "ran:gone"
