from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    GenerationBounds,
    InferenceEvent,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
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
    ToolRun,
    ToolSpec,
    TurnCapabilities,
    TurnEngine,
    TurnEvent,
)
from cortex_core.tool_replay import REPLAYED_FAILED, REPLAYED_OK, RunLog, replay_runs

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
