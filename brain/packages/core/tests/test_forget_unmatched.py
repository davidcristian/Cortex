from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
import swap_harness as harness

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    GLOBAL_MEMORY_SCOPE,
    CompositeToolRegistry,
    DispatchPolicy,
    ForgetChosenTool,
    GenerationBounds,
    HashEmbedder,
    InferenceEvent,
    InMemoryMemoryStore,
    InMemorySessionStore,
    InMemoryToolRegistry,
    JsonSchema,
    MalformedToolCallError,
    MemoryRecaller,
    MemoryRecord,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    Role,
    SystemClock,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

_AT = datetime(2026, 10, 30, 3, 0, 0, tzinfo=UTC)
_HELD = "User: Remember that my locker code is 7319.\nAssistant: Noted."


class _Clock:
    def now(self) -> datetime:
        return _AT


class _TickingClock:
    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        self._ticks += 1
        return _AT + timedelta(seconds=self._ticks)


class _RoundsBackend:
    """Emits one scripted round of calls per step, then a plain answer; an empty round fails."""

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
        if not self._rounds[step]:
            msg = "malformed tool-call arguments from llama-server"
            raise MalformedToolCallError(msg, tool_name=FORGET_CHOSEN_TOOL_NAME)
        for call in self._rounds[step]:
            yield call


async def _empty(arguments: Mapping[str, object]) -> ToolResult:
    del arguments
    return ToolResult(call_id="", content="no files", trust=Trust.TRUSTED, matched_nothing=True)


def _forget(text: str, index: int = 0) -> ToolCall:
    return ToolCall(id=f"f{index}", name=FORGET_CHOSEN_TOOL_NAME, arguments={"text": text})


async def _loop(rounds: Sequence[Sequence[ToolCall]], *, approve: bool = True) -> TaintLedger:
    """Run one loop over the real ``forget_memories`` and a tool that finds nothing."""
    store = InMemoryMemoryStore()
    await store.add(MemoryRecord(id="m", text=_HELD, embedding=(1.0, 0.0), at=_AT))
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    remote = InMemoryToolRegistry({"find": (ToolSpec("find", "find", {}), _empty)})
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget], remote=remote),
        RecordingAuditSink(),
        _Clock(),
        confirmer=RecordingConfirmer(answer=approve),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=dispatcher, clock=_Clock(), turn_id="t", taint=taint, nonce="n", session_id="s"
    )
    working = [Message(role=Role.USER, text="remember it", at=_AT, turn_id="t")]
    async for _ in stream_tool_loop(_RoundsBackend(rounds), "m", working, context):
        pass
    return taint


@pytest.mark.parametrize(
    ("rounds", "approve", "counts"),
    [
        ([[_forget("Fiat")]], True, (1, 1)),
        ([[_forget("Fiat"), _forget("Luca", 1)]], True, (2, 2)),
        ([[_forget("7319")]], True, (1, 0)),
        ([[_forget("7319")]], False, (1, 0)),
        ([[_forget("Fiat")], [_forget("7319", 1)]], True, (2, 1)),
        ([[ToolCall(id="x", name="find", arguments={})]], True, (0, 0)),
    ],
)
async def test_the_ledger_counts_each_forget_call_and_each_that_matched_nothing(
    *, rounds: list[list[ToolCall]], approve: bool, counts: tuple[int, int]
) -> None:
    taint = await _loop(rounds, approve=approve)
    assert (taint.forget_calls, taint.forget_unmatched) == counts
    assert taint.forget_asked is (counts[0] > 0)


def test_naming_no_forget_call_leaves_the_turn_unmarked() -> None:
    taint = TaintLedger()
    taint.name_forget(0)
    assert (taint.forget_asked, taint.forget_calls) == (False, 0)
    taint.name_forget(1)
    taint.name_forget(0)
    assert (taint.forget_asked, taint.forget_calls) == (True, 1)


@pytest.mark.parametrize(
    ("rounds", "kept"), [([[_forget("Fiat")]], 1), ([[_forget("Fiat")], []], 0)]
)
async def test_an_unreadable_forget_after_one_that_matched_nothing_still_keeps_nothing(
    *, rounds: list[list[ToolCall]], kept: int
) -> None:
    store = InMemoryMemoryStore()
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _TickingClock(),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    caps = TurnCapabilities(
        memory=MemoryRecaller(store, HashEmbedder(), SystemClock()), tools=dispatcher
    )
    engine = TurnEngine(
        InMemorySessionStore(), _RoundsBackend(rounds), _TickingClock(), capabilities=caps
    )
    query = "Please remember this: my car is a red Fiat."
    async for _ in engine.handle_turn("s", query, turn_id="t-1"):
        pass
    assert len(await store.search(await HashEmbedder().embed("Fiat"), k=5)) == kept


@pytest.mark.parametrize(
    ("rounds", "kept"), [([[_forget("Fiat")]], 1), ([[_forget("Fiat")], []], 0)]
)
async def test_a_deep_phase_whose_forget_matched_nothing_keeps_only_a_readable_turn(
    *, rounds: list[list[ToolCall]], kept: int
) -> None:
    store = InMemoryMemoryStore()
    forget = ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([forget]),
        RecordingAuditSink(),
        _TickingClock(),
        policy=DispatchPolicy(
            record_cards={FORGET_CHOSEN_TOOL_NAME: forget}, notes={FORGET_CHOSEN_TOOL_NAME: forget}
        ),
    )
    caps = TurnCapabilities(
        memory=MemoryRecaller(store, HashEmbedder(), SystemClock()), tools=dispatcher
    )
    sessions = InMemorySessionStore()
    query = "Please remember this: my car is a red Fiat."
    await sessions.append(
        harness.SESSION, Message(role=Role.USER, text=query, at=_AT, turn_id=harness.TURN)
    )
    phase = BrainPhase(sessions, _RoundsBackend(rounds), _TickingClock(), "brain", caps)
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    async for _ in phase.run(record):
        pass
    assert len(await store.search(await HashEmbedder().embed("Fiat"), k=5)) == kept
