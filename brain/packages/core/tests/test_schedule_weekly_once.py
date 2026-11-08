from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest
import swap_harness as harness
from swap_harness import Fakes, ScriptedBrainBackend, TickingClock

from cortex_core import (
    SCHEDULE_TOOL_NAME,
    InMemoryHandoffStore,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    Role,
    StopLedger,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEvent,
)
from cortex_core.closing_notes import limit_notes
from cortex_core.schedule_verbs import EDIT_SCHEDULED_TOOL_NAME
from cortex_core.schedule_weekly import ONCE_STORED_NOTE, WEEKLY_DAY_MSG, stores_once
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 11, 8, 3, 0, 0, tzinfo=UTC)
_STRETCH = "Remind me Tuesday at 8 to stretch, keep it going."
_WEEKLY = {"text": "stretch", "at_time": "08:00", "on_days": ["tue"]}
_ONCE = {"text": "stretch", "at": "2026-11-10T08:00:00"}


@pytest.mark.parametrize(
    ("name", "arguments", "failed", "once"),
    [
        (SCHEDULE_TOOL_NAME, _ONCE, False, True),
        (SCHEDULE_TOOL_NAME, {"in_seconds": 3600}, False, True),
        (SCHEDULE_TOOL_NAME, {**_ONCE, "every_seconds": 0}, False, True),
        (SCHEDULE_TOOL_NAME, {**_ONCE, "every_seconds": 3600}, False, False),
        (SCHEDULE_TOOL_NAME, _WEEKLY, False, False),
        (SCHEDULE_TOOL_NAME, {"at_time": "08:00"}, False, False),
        (SCHEDULE_TOOL_NAME, _ONCE, True, False),
        (EDIT_SCHEDULED_TOOL_NAME, {"id": "i", **_ONCE}, False, False),
    ],
)
def test_only_a_schedule_call_that_ran_with_no_repeat_field_stores_once(
    name: str, arguments: Mapping[str, object], *, failed: bool, once: bool
) -> None:
    call = ToolCall(id="c", name=name, arguments=arguments)
    result = ToolResult(call_id="c", content="scheduled", is_error=failed, trust=Trust.TRUSTED)
    assert stores_once(call, result) is once


def _dispatcher() -> ToolDispatcher:
    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        return "scheduled"

    spec = ToolSpec(name=SCHEDULE_TOOL_NAME, description="s", parameters={})
    registry = InMemoryToolRegistry({SCHEDULE_TOOL_NAME: (spec, handler)})
    return ToolDispatcher(registry, RecordingAuditSink(), TickingClock())


async def _taint(calls: Sequence[Mapping[str, object]]) -> TaintLedger:
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=_dispatcher(),
        clock=TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=_STRETCH,
    )
    working = [Message(role=Role.USER, text=_STRETCH, at=_AT, turn_id="t")]
    scripted = [
        ToolCall(id=f"c{index}", name=SCHEDULE_TOOL_NAME, arguments=arguments)
        for index, arguments in enumerate(calls)
    ]
    backend = ScriptedBrainBackend(chunks=("done",), tool_calls=scripted)
    _ = [event async for event in stream_tool_loop(backend, "m", working, context)]
    return taint


@pytest.mark.parametrize(
    ("calls", "flagged"),
    [
        ([_WEEKLY, _ONCE], True),
        ([_WEEKLY, _WEEKLY], False),
        ([_ONCE], False),
        ([_ONCE, _WEEKLY], False),
    ],
)
async def test_a_turn_is_flagged_once_a_one_time_item_is_stored_after_a_weekly_refusal(
    calls: Sequence[Mapping[str, object]], *, flagged: bool
) -> None:
    assert (await _taint(calls)).once_after_weekly is flagged


@pytest.mark.parametrize(
    "reply",
    [
        "I'll remind you on Tuesday at 8 to stretch.",
        "Done: a one-time reminder for Tuesday at 08:00.",
        "I've set it for every Tuesday at 8.",
    ],
)
@pytest.mark.parametrize("flagged", [True, False])
def test_the_note_follows_any_reply_of_a_flagged_turn(reply: str, *, flagged: bool) -> None:
    parts = [reply]
    taint = TaintLedger(once_after_weekly=flagged)
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=""))
    assert "".join(parts).endswith(ONCE_STORED_NOTE) is flagged


def _shown(events: Sequence[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def test_the_flag_survives_the_model_swap_through_the_handoff_store() -> None:
    slot = harness.prepared_slot(taint=TaintLedger(once_after_weekly=True))
    store = InMemoryHandoffStore()
    await store.put(
        slot.snapshot(turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT)
    )
    loaded = await store.get(harness.TURN)
    assert loaded is not None
    assert loaded.taint_ledger().once_after_weekly
    live = harness.build_harness()
    await live.seed_session()
    shown = _shown(await harness.run_handoff(live, slot))
    assert shown.endswith(ONCE_STORED_NOTE)


def _round(call_id: str, arguments: Mapping[str, object], said: str) -> tuple[Message, Message]:
    call = ToolCall(id=call_id, name=SCHEDULE_TOOL_NAME, arguments=arguments)
    return (
        Message(role=Role.ASSISTANT, text="", at=_AT, turn_id=harness.TURN, tool_calls=(call,)),
        Message(role=Role.TOOL, text=said, at=_AT, turn_id=harness.TURN, tool_call_id=call_id),
    )


@pytest.mark.parametrize(("said", "flagged"), [(WEEKLY_DAY_MSG, True), ("scheduled", False)])
async def test_a_deep_one_time_store_after_the_cortex_refusal_shows_the_note(
    said: str, *, flagged: bool
) -> None:
    deep = ToolCall(id="c1", name=SCHEDULE_TOOL_NAME, arguments=_ONCE)
    live = harness.build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("done",), tool_calls=(deep,))),
        capabilities=TurnCapabilities(tools=_dispatcher()),
    )
    await live.seed_session()
    slot = harness.prepared_slot(tail=_round("c0", _WEEKLY, said))
    shown = _shown(await harness.run_handoff(live, slot))
    assert shown.endswith(ONCE_STORED_NOTE) is flagged


@pytest.mark.parametrize("calls", [[_WEEKLY, _WEEKLY, _ONCE], [_WEEKLY, _ONCE, _WEEKLY]])
async def test_a_turn_that_also_stores_a_weekly_rule_gets_a_note_true_of_both(
    calls: Sequence[Mapping[str, object]],
) -> None:
    taint = await _taint(calls)
    parts = ["Done: every Tuesday at 8, and once on 2026-11-10."]
    list(limit_notes(StopLedger(), (), parts, caps=TurnCapabilities(), taint=taint, query=_STRETCH))
    assert "".join(parts).endswith(ONCE_STORED_NOTE)
    assert ONCE_STORED_NOTE.startswith("\n\n(A reminder set in this turn is for one day only.")
