from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
import swap_harness as harness

from cortex_core import (
    FORGET_CHOSEN_TOOL_NAME,
    FORGET_NOT_KEPT_NOTE,
    GLOBAL_MEMORY_SCOPE,
    UNFORGOTTEN_CLAIM_NOTE,
    UNKEPT_CLAIM_NOTE,
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
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnCapabilities,
    TurnEngine,
)
from cortex_core.brain_phase import BrainPhase
from cortex_core.dispatch import UNASKED_MSG, DispatchRefusal
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


_REMEMBER_FIAT = "Please remember this: my car is a red Fiat."
_REMEMBER_AND_FORGET = "Remember that my car is a red Fiat, and forget the locker code."


class _ReplyBackend:
    """Writes one round of ``calls``, then ``reply``."""

    def __init__(self, calls: Sequence[ToolCall], reply: str = "Noted.") -> None:
        self._calls = list(calls)
        self._reply = reply
        self.seen: list[str] = []

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
        self.seen.append(messages[-1].text)
        calls, self._calls = self._calls, []
        for call in calls:
            yield call
        if not calls:
            yield TextChunk(self._reply)


class _Rig:
    """A store holding one exchange, the real ``forget_memories`` and an engine over them."""

    def __init__(self, *, approve: bool = True) -> None:
        self.store = InMemoryMemoryStore()
        self.sessions = InMemorySessionStore()
        self.audit = RecordingAuditSink()
        self.confirmer = RecordingConfirmer(answer=approve)
        forget = ForgetChosenTool(self.store, GLOBAL_MEMORY_SCOPE)
        self.dispatcher = ToolDispatcher(
            CompositeToolRegistry([forget]),
            self.audit,
            _TickingClock(),
            confirmer=self.confirmer,
            policy=DispatchPolicy(
                record_cards={FORGET_CHOSEN_TOOL_NAME: forget},
                notes={FORGET_CHOSEN_TOOL_NAME: forget},
            ),
        )
        self.caps = TurnCapabilities(
            memory=MemoryRecaller(self.store, HashEmbedder(), SystemClock()), tools=self.dispatcher
        )

    async def seed(self) -> None:
        text = "User: Please remember this: my car is a red Fiat.\nAssistant: Noted."
        embedding = tuple(await HashEmbedder().embed(text))
        await self.store.add(MemoryRecord(id="m", text=text, embedding=embedding, at=_AT))

    async def turn(self, query: str, backend: _ReplyBackend, session: str = "s") -> str:
        engine = TurnEngine(self.sessions, backend, _TickingClock(), capabilities=self.caps)
        events = engine.handle_turn(session, query, turn_id=f"t-{session}")
        return "".join([event.text async for event in events if isinstance(event, TextDelta)])

    async def held(self) -> list[str]:
        found = await self.store.search(await HashEmbedder().embed("Fiat"), k=5)
        return [hit.record.text for hit in found if "Fiat" in hit.record.text]


async def test_a_forget_call_on_a_request_to_remember_a_stored_fact_keeps_old_and_new() -> None:
    rig = _Rig()
    await rig.seed()
    reply = await rig.turn(_REMEMBER_FIAT, _ReplyBackend([_forget("Fiat")]))
    assert reply == "Noted."
    assert rig.confirmer.requests == ()
    (refused,) = rig.audit.records
    assert (refused.name, refused.ok, refused.detail) == (
        FORGET_CHOSEN_TOOL_NAME,
        False,
        UNASKED_MSG,
    )
    assert len(await rig.held()) == 2


@pytest.mark.parametrize(
    ("query", "says_not_kept"),
    [(_REMEMBER_FIAT, False), (_REMEMBER_AND_FORGET, True), ("Forget the Fiat.", True)],
)
async def test_the_model_reads_that_nothing_is_kept_only_when_that_is_true(
    *, query: str, says_not_kept: bool
) -> None:
    rig = _Rig()
    await rig.seed()
    backend = _ReplyBackend([_forget("Fiat")])
    await rig.turn(query, backend)
    assert (FORGET_NOT_KEPT_NOTE in backend.seen[-1]) is says_not_kept
    assert (UNASKED_MSG in backend.seen[-1]) is not says_not_kept


@pytest.mark.parametrize("refusal", list(DispatchRefusal))
async def test_a_refused_forget_ends_with_the_note_unless_it_was_refused_as_unasked(
    refusal: DispatchRefusal,
) -> None:
    result = await _Rig().dispatcher.dispatch(_forget("Fiat"), refusal=refusal)
    assert (FORGET_NOT_KEPT_NOTE in result.content) is (refusal is not DispatchRefusal.UNASKED)


@pytest.mark.parametrize(
    ("reply", "note"),
    [
        ("I have removed your car from my memory.", UNFORGOTTEN_CLAIM_NOTE),
        ("I've noted that your car is a red Fiat.", ""),
    ],
)
async def test_the_reply_after_a_refused_forget_gets_only_the_note_that_is_true(
    *, reply: str, note: str
) -> None:
    rig = _Rig()
    await rig.seed()
    shown = await rig.turn(_REMEMBER_FIAT, _ReplyBackend([_forget("Fiat")], reply))
    assert shown == reply + note
    assert UNKEPT_CLAIM_NOTE not in shown
    assert len(await rig.held()) == 2


async def test_a_request_to_remember_and_to_forget_still_shows_the_card_and_runs() -> None:
    rig = _Rig()
    await rig.seed()
    shown = await rig.turn(_REMEMBER_AND_FORGET, _ReplyBackend([_forget("Fiat")]))
    assert len(rig.confirmer.requests) == 1
    assert await rig.held() == []
    assert shown == "Noted." + UNKEPT_CLAIM_NOTE


async def test_the_refusal_lasts_one_turn_and_the_next_message_can_forget() -> None:
    rig = _Rig()
    await rig.seed()
    await rig.turn(_REMEMBER_FIAT, _ReplyBackend([_forget("Fiat")]))
    assert len(await rig.held()) == 2
    await rig.turn("Yes, forget the Fiat.", _ReplyBackend([_forget("Fiat")]))
    assert len(rig.confirmer.requests) == 1
    assert await rig.held() == []


@pytest.mark.parametrize(
    ("query", "counted"), [(_REMEMBER_FIAT, 0), (_REMEMBER_AND_FORGET, 1), ("Forget the Fiat.", 1)]
)
async def test_only_a_forget_call_the_message_can_ask_for_counts_in_the_ledger(
    *, query: str, counted: int
) -> None:
    rig = _Rig()
    taint = TaintLedger()
    context = ToolLoopContext(
        dispatcher=rig.dispatcher,
        clock=_TickingClock(),
        turn_id="t",
        taint=taint,
        nonce="n",
        session_id="s",
        query=query,
    )
    working = [Message(role=Role.USER, text=query, at=_AT, turn_id="t")]
    backend = _ReplyBackend([_forget("Fiat")])
    async for _ in stream_tool_loop(backend, "m", working, context):
        pass
    assert (taint.forget_asked, taint.forget_calls) == (counted > 0, counted)


async def test_a_forget_the_model_wrote_unreadably_still_keeps_the_turn_out() -> None:
    store = InMemoryMemoryStore()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([ForgetChosenTool(store, GLOBAL_MEMORY_SCOPE)]),
        RecordingAuditSink(),
        _TickingClock(),
    )
    caps = TurnCapabilities(
        memory=MemoryRecaller(store, HashEmbedder(), SystemClock()), tools=dispatcher
    )
    engine = TurnEngine(
        InMemorySessionStore(), _RoundsBackend([[]]), _TickingClock(), capabilities=caps
    )
    async for _ in engine.handle_turn("s", _REMEMBER_FIAT, turn_id="t-1"):
        pass
    assert not await store.search(await HashEmbedder().embed("Fiat"), k=5)


async def test_a_deep_phase_refuses_a_forget_call_on_a_request_to_remember() -> None:
    rig = _Rig()
    await rig.seed()
    await rig.sessions.append(
        harness.SESSION,
        Message(role=Role.USER, text=_REMEMBER_FIAT, at=_AT, turn_id=harness.TURN),
    )
    phase = BrainPhase(
        rig.sessions, _ReplyBackend([_forget("Fiat")]), _TickingClock(), "brain", rig.caps
    )
    record = harness.prepared_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=_AT
    )
    async for _ in phase.run(record):
        pass
    assert rig.confirmer.requests == ()
    assert len(await rig.held()) == 2
