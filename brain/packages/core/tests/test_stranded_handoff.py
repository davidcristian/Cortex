import logging
from collections.abc import Sequence

import pytest
import swap_harness as harness
from swap_harness import RecordingHandoffStore, RecordingSessionStore, TickingClock

from cortex_core import (
    BaselineTiers,
    HandoffState,
    InMemorySessionStore,
    Message,
    RecordingSleeper,
    Role,
    ScriptedInferenceBackend,
    ScriptedModelHost,
    SessionStoreError,
    SystemClock,
    TextChunk,
    ToolRun,
    TurnCompleted,
    TurnEngine,
    recover_handoffs,
)
from cortex_core.escalate import ESCALATE_TOOL_NAME
from cortex_core.reply_notes import model_text
from cortex_core.stranded_handoff import (
    UNANSWERED_HANDOFF_NOTE,
    UNANSWERED_HANDOFF_NOTES,
    UNANSWERED_RUN,
    UNSURE_HANDOFF_NOTE,
    unanswered_handoff_note,
)
from cortex_core.tool_replay import (
    HANDOFF_STARTED,
    REPLAYED_FAILED,
    REPLAYED_OK,
    REPLAYED_UNANSWERED,
    replay_runs,
    runs_line,
)

_STARTED = ToolRun(ESCALATE_TOOL_NAME, ok=True)
_FRENCH = "Je veux que vous demandiez au modèle profond pourquoi le ciel est bleu"


class _UnreadableSessions(InMemorySessionStore):
    def __init__(self) -> None:
        super().__init__()
        self.unreadable = False

    async def history(self, session_id: str) -> Sequence[Message]:
        if self.unreadable:
            msg = f"history of session {session_id!r} failed"
            raise SessionStoreError(msg)
        return await super().history(session_id)


async def _seed(
    sessions: InMemorySessionStore, asked: str = harness.USER_TEXT, *, deep: str | None = None
) -> None:
    at = TickingClock().now()
    turn = [
        Message(role=Role.USER, text=asked, at=at, turn_id=harness.TURN),
        Message(
            role=Role.ASSISTANT,
            text=harness.CORTEX_TEXT,
            at=at,
            turn_id=harness.TURN,
            runs=(_STARTED,),
        ),
    ]
    if deep is not None:
        turn.append(Message(role=Role.ASSISTANT, text=deep, at=at, turn_id=harness.TURN))
    for message in turn:
        await sessions.append(harness.SESSION, message)


async def _recover(sessions: InMemorySessionStore) -> RecordingHandoffStore:
    handoffs = RecordingHandoffStore()
    stranded = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=SystemClock().now()
    )
    await handoffs.put(stranded)
    await recover_handoffs(
        handoffs,
        ScriptedModelHost(running=["cortex"]),
        harness.plan(),
        BaselineTiers(),
        sessions=sessions,
        clock=TickingClock(),
        sleeper=RecordingSleeper(),
    )
    return handoffs


async def _failed(handoffs: RecordingHandoffStore) -> bool:
    record = await handoffs.get(harness.TURN)
    return record is not None and record.state is HandoffState.FAILED


def _engine(sessions: InMemorySessionStore) -> TurnEngine:
    backend = ScriptedInferenceBackend([[TextChunk("ten")], [TextChunk("twelve")]])
    return TurnEngine(sessions, backend, SystemClock())


async def _reply(engine: TurnEngine, text: str, turn_id: str) -> str:
    events = [event async for event in engine.handle_turn(harness.SESSION, text, turn_id=turn_id)]
    return next(event.full_text for event in events if isinstance(event, TurnCompleted))


async def test_recovery_stores_in_the_chat_that_the_handoff_got_no_answer() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions)
    assert await _failed(await _recover(sessions))
    history = await sessions.history(harness.SESSION)
    assert len(history) == 3
    record = history[-1]
    assert (record.role, record.text, record.turn_id, record.runs) == (
        Role.ASSISTANT,
        UNANSWERED_HANDOFF_NOTE,
        harness.TURN,
        (UNANSWERED_RUN,),
    )


async def test_the_record_is_written_in_the_language_of_the_request() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions, _FRENCH)
    await _recover(sessions)
    assert (await sessions.history(harness.SESSION))[-1].text == UNANSWERED_HANDOFF_NOTES["fr"]


async def test_a_handoff_whose_deep_reply_is_stored_gets_no_record() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions, deep="the proof")
    assert await _failed(await _recover(sessions))
    history = await sessions.history(harness.SESSION)
    assert [message.text for message in history[1:]] == [harness.CORTEX_TEXT, "the proof"]
    assert unanswered_handoff_note(history) == ""


async def test_a_chat_that_cannot_be_read_gets_the_record_that_says_maybe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = _UnreadableSessions()
    await _seed(sessions, deep="the proof")
    sessions.unreadable = True
    with caplog.at_level(logging.ERROR, logger="cortex_core.stranded_handoff"):
        assert await _failed(await _recover(sessions))
    sessions.unreadable = False
    history = await sessions.history(harness.SESSION)
    assert (history[-1].text, history[-1].runs) == (UNSURE_HANDOFF_NOTE, (UNANSWERED_RUN,))
    assert unanswered_handoff_note(history) == f"\n\n{UNSURE_HANDOFF_NOTE}"
    assert [record.message for record in caplog.records] == [
        "could not read the chat of a handoff the restart ended"
    ]


async def test_a_chat_that_cannot_be_written_still_has_its_handoff_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = RecordingSessionStore(fail_at=3)
    await _seed(sessions)
    with caplog.at_level(logging.ERROR, logger="cortex_core.stranded_handoff"):
        assert await _failed(await _recover(sessions))
    assert len(await sessions.history(harness.SESSION)) == 2
    assert [record.message for record in caplog.records] == [
        "could not store that a handoff the restart ended got no answer"
    ]


async def test_the_next_reply_says_once_that_the_handoff_got_no_answer() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions)
    await _recover(sessions)
    engine = _engine(sessions)
    first = await _reply(engine, "5 plus 5?", "t-2")
    assert first == f"ten\n\n{UNANSWERED_HANDOFF_NOTE}"
    assert model_text(first).rstrip() == "ten"
    assert (await sessions.history(harness.SESSION))[-1].text == first
    assert await _reply(engine, "6 plus 6?", "t-3") == "twelve"


async def test_a_reply_stored_without_the_note_leaves_it_for_the_next_reply() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions)
    await _recover(sessions)
    bare = Message(role=Role.ASSISTANT, text="cut", at=TickingClock().now(), turn_id="t-2")
    await sessions.append(harness.SESSION, bare)
    assert (
        await _reply(_engine(sessions), "5 plus 5?", "t-3") == f"ten\n\n{UNANSWERED_HANDOFF_NOTE}"
    )


async def test_a_handoff_that_completed_gets_no_note() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions, deep="the proof")
    await _recover(sessions)
    assert await _reply(_engine(sessions), "5 plus 5?", "t-2") == "ten"


def test_a_declined_handoff_and_an_empty_chat_get_no_note() -> None:
    declined = Message(
        role=Role.ASSISTANT,
        text="I did not hand it over.",
        at=TickingClock().now(),
        turn_id="t-1",
        runs=(UNANSWERED_RUN,),
    )
    assert unanswered_handoff_note([declined]) == ""
    assert unanswered_handoff_note([]) == ""


async def test_the_model_reads_the_handoff_as_unanswered_and_its_record_as_failed() -> None:
    sessions = InMemorySessionStore()
    await _seed(sessions)
    await _recover(sessions)
    replayed = replay_runs(await sessions.history(harness.SESSION))
    outcomes = [message.text for message in replayed if message.role is Role.TOOL]
    assert outcomes == [REPLAYED_UNANSWERED, REPLAYED_FAILED]
    assert REPLAYED_OK not in outcomes


def test_a_started_handoff_is_not_written_as_a_success_on_the_runs_line() -> None:
    runs = (ToolRun("read", ok=True), _STARTED, UNANSWERED_RUN)
    assert runs_line(runs) == (
        f"Tools run: read (succeeded), {ESCALATE_TOOL_NAME} ({HANDOFF_STARTED}), "
        f"{ESCALATE_TOOL_NAME} (failed)"
    )
