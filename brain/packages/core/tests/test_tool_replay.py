from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MemoryRecaller,
    Message,
    RecordingAuditSink,
    Role,
    StatusUpdate,
    SystemClock,
    TextChunk,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolOutcome,
    ToolResult,
    ToolRun,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEngine,
    TurnEvent,
)
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.tool_replay import (
    RECALLED_RUNS_NOTE,
    REPLAYED_FAILED,
    REPLAYED_OK,
    REPLAYED_UNANSWERED,
    RunLog,
    replay_runs,
)
from cortex_core.turn_context import MEMORY_HEADER
from cortex_core.turn_output import render_exchange

_AT = datetime(2026, 10, 10, 6, 0, tzinfo=UTC)
_RAW_RESULT = "the raw result the store never keeps"


def _message(role: Role, text: str, *, runs: tuple[ToolRun, ...] = ()) -> Message:
    return Message(role=role, text=text, at=_AT, turn_id="t-1", runs=runs)


def test_a_run_log_keeps_each_outcome_and_passes_every_event_through() -> None:
    log = RunLog()
    events: list[TurnEvent] = [
        TextDelta("checking"),
        ToolOutcome(tool_name="send_email", ok=True),
        StatusUpdate(state="calling", detail="x"),
        ToolOutcome(tool_name="read_email", ok=False),
    ]
    assert [log.note(event) for event in events] == events
    assert log.runs == (ToolRun("send_email", ok=True), ToolRun("read_email", ok=False))


def test_a_history_without_runs_is_replayed_unchanged() -> None:
    history = [_message(Role.USER, "hi"), _message(Role.ASSISTANT, "hello")]
    assert replay_runs(history) == history


def test_a_reply_with_runs_is_preceded_by_its_calls_and_their_fixed_outcomes() -> None:
    runs = (ToolRun("send_email", ok=True), ToolRun("read_email", ok=False))
    reply = _message(Role.ASSISTANT, "sent", runs=runs)
    user = _message(Role.USER, "send it")
    call_step, sent, read, replayed_reply = replay_runs([user, reply])[1:]
    assert [(c.id, c.name, c.arguments) for c in call_step.tool_calls] == [
        ("replay-1-0", "send_email", {}),
        ("replay-1-1", "read_email", {}),
    ]
    assert (call_step.role, call_step.text) == (Role.ASSISTANT, "")
    assert (sent.role, sent.tool_call_id, sent.text) == (Role.TOOL, "replay-1-0", REPLAYED_OK)
    assert (read.role, read.tool_call_id, read.text) == (Role.TOOL, "replay-1-1", REPLAYED_FAILED)
    assert replayed_reply is reply
    assert {m.turn_id for m in (call_step, sent, read)} == {"t-1"}


def test_two_replies_get_distinct_call_ids() -> None:
    reply = _message(Role.ASSISTANT, "done", runs=(ToolRun("read", ok=True),))
    replayed = replay_runs([reply, reply])
    ids = [m.tool_call_id for m in replayed if m.role is Role.TOOL]
    assert ids == ["replay-0-0", "replay-1-0"]


def _outcomes(history: list[Message]) -> list[str]:
    return [m.text for m in replay_runs(history) if m.role is Role.TOOL]


def _handoff_turn(turn_id: str, *, ok: bool = True) -> list[Message]:
    runs = (ToolRun("read", ok=True), ToolRun(ESCALATE_TOOL_NAME, ok=ok))
    return [
        Message(role=Role.USER, text="prove it", at=_AT, turn_id=turn_id),
        Message(role=Role.ASSISTANT, text="handing over", at=_AT, turn_id=turn_id, runs=runs),
    ]


def test_a_handoff_with_no_stored_deep_reply_is_replayed_as_unanswered() -> None:
    assert _outcomes(_handoff_turn("t-1")) == [REPLAYED_OK, REPLAYED_UNANSWERED]


def test_a_handoff_whose_deep_reply_is_stored_is_replayed_as_a_success() -> None:
    deep = Message(role=Role.ASSISTANT, text="the proof", at=_AT, turn_id="t-1")
    assert _outcomes([*_handoff_turn("t-1"), deep]) == [REPLAYED_OK, REPLAYED_OK]


def test_a_later_turns_reply_does_not_answer_an_earlier_handoff() -> None:
    later = Message(role=Role.ASSISTANT, text="ten", at=_AT, turn_id="t-2")
    asked = Message(role=Role.USER, text="5 plus 5?", at=_AT, turn_id="t-2")
    history = [*_handoff_turn("t-1"), asked, later]
    assert _outcomes(history) == [REPLAYED_OK, REPLAYED_UNANSWERED]


def test_a_declined_handoff_is_replayed_as_failed() -> None:
    assert _outcomes(_handoff_turn("t-1", ok=False)) == [REPLAYED_OK, REPLAYED_FAILED]


class _TwoTurnBackend:
    """Calls ``read`` on the first request of turn one, then answers in text; records requests."""

    def __init__(self) -> None:
        self.seen: list[list[Message]] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema, bounds
        self.seen.append(list(messages))
        if len(self.seen) == 1:
            yield ToolCall(id="c1", name="read", arguments={"path": "/notes"})
            return
        yield TextChunk("done")


async def _drain(events: AsyncGenerator[TurnEvent, None]) -> None:
    async for _event in events:
        pass


def _engine(store: InMemorySessionStore, backend: _TwoTurnBackend, *, fails: bool) -> TurnEngine:
    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        if fails:
            msg = "the disk is gone"
            raise ToolError(msg)
        return _RAW_RESULT

    spec = ToolSpec(name="read", description="read a file", parameters={"type": "object"})
    registry = InMemoryToolRegistry({"read": (spec, handler)})
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), SystemClock())
    return TurnEngine(
        store, backend, SystemClock(), capabilities=TurnCapabilities(tools=dispatcher)
    )


@pytest.mark.parametrize("outcome", [REPLAYED_OK, REPLAYED_FAILED])
async def test_a_later_turn_reads_that_an_earlier_one_ran_a_tool(outcome: str) -> None:
    fails = outcome == REPLAYED_FAILED
    store = InMemorySessionStore()
    backend = _TwoTurnBackend()
    engine = _engine(store, backend, fails=fails)
    await _drain(engine.handle_turn("s", "read my notes", turn_id="t-1"))
    _user, reply = await store.history("s")
    assert reply.runs == (ToolRun("read", ok=not fails),)
    await _drain(engine.handle_turn("s", "read them again", turn_id="t-2"))
    later = backend.seen[-1]
    assert [m.role for m in later] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.USER,
    ]
    assert later[2].tool_calls[0].name == "read"
    assert later[2].tool_calls[0].arguments == {}
    assert later[3].text == outcome
    assert later[4].text == "done"
    assert all(_RAW_RESULT not in m.text for m in later)


def test_an_exchange_without_runs_is_recorded_as_the_message_and_the_reply() -> None:
    assert render_exchange("hi", "hello") == "User: hi\nAssistant: hello"


def test_a_recorded_exchange_names_each_run_in_order_with_its_outcome() -> None:
    runs = (ToolRun("list_scheduled", ok=True), ToolRun("schedule_task", ok=False))
    assert render_exchange("remind me", "done", runs) == (
        "User: remind me\nTools run: list_scheduled (succeeded), schedule_task (failed)\n"
        "Assistant: done"
    )


@pytest.mark.parametrize("fails", [False, True])
async def test_another_chat_recalls_the_run_under_a_note_that_it_ran_there_only(
    *, fails: bool
) -> None:
    async def handler(arguments: Mapping[str, object]) -> ToolResult:
        del arguments
        if fails:
            msg = "the disk is gone"
            raise ToolError(msg)
        return ToolResult(call_id="", content="notes", trust=Trust.TRUSTED)

    spec = ToolSpec(name="read", description="read a file", parameters={"type": "object"})
    registry = InMemoryToolRegistry({"read": (spec, handler)})
    recaller = MemoryRecaller(InMemoryMemoryStore(), HashEmbedder(), SystemClock())
    caps = TurnCapabilities(
        tools=ToolDispatcher(registry, RecordingAuditSink(), SystemClock()), memory=recaller
    )
    backend = _TwoTurnBackend()
    engine = TurnEngine(InMemorySessionStore(), backend, SystemClock(), capabilities=caps)
    await _drain(engine.handle_turn("first", "read my notes", turn_id="t-1"))
    await _drain(engine.handle_turn("second", "read my notes", turn_id="t-2"))
    recalled = backend.seen[-1][1]
    assert recalled.role is Role.SYSTEM
    assert recalled.text == (
        f"{MEMORY_HEADER} {RECALLED_RUNS_NOTE}\n"
        "- (just now) User: read my notes\n"
        f"Tools run: read ({'failed' if fails else 'succeeded'})\n"
        "Assistant: done"
    )
