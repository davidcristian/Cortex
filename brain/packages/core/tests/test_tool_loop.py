from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from cortex_core import (
    ALWAYS_SALIENT,
    BUDGET_EXHAUSTED_MSG,
    MAX_CALLS_PER_ROUND,
    REDUNDANT_MSG,
    REPEAT_SALIENCE,
    ROUND_OVERSIZED_MSG,
    CadenceWatch,
    DecodeCadence,
    DecodeStop,
    DispatchPolicy,
    EscalationSlot,
    GenerationBounds,
    ImagePart,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    Provenance,
    RecordingAuditSink,
    Role,
    SaliencePolicy,
    SourceKind,
    StopLedger,
    StopReason,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.loop_events import ToolStep
from cortex_core.tool_budget import (
    MAX_TOOL_DISPATCHES,
    UNIFORM_COST,
    DispatchBudget,
    ToolCostPolicy,
)
from cortex_core.tool_loop import MAX_TOOL_STEPS, ToolLoopContext, stream_tool_loop

_START = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)


class _TickingClock:
    """A clock whose every reading is one second after the previous one."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        at = _START + timedelta(seconds=self._ticks)
        self._ticks += 1
        return at


class _MultiCallBackend:
    """Emits ``per_round`` tool calls every inference step and never a final answer."""

    def __init__(self, per_round: int) -> None:
        self._per_round = per_round
        self.rounds = 0
        self.seen: list[Sequence[Message]] = []

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
        self.rounds += 1
        self.seen.append(list(messages))
        yield TextChunk("working ")
        for index in range(self._per_round):
            # The arguments are distinct per call and per round, so these fixtures test the
            # budget alone: an identical repeat would be refused by the salience policy first.
            yield ToolCall(
                id=f"r{self.rounds}c{index}",
                name="noop",
                arguments={"call": f"r{self.rounds}c{index}"},
            )


class _ScriptedBackend(_MultiCallBackend):
    """Emits a fixed sequence of tool names every round, so one round can mix prices."""

    def __init__(self, names: Sequence[str]) -> None:
        super().__init__(per_round=len(names))
        self._names = list(names)

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
        self.rounds += 1
        self.seen.append(list(messages))
        for index, name in enumerate(self._names):
            yield ToolCall(
                id=f"r{self.rounds}c{index}",
                name=name,
                arguments={"call": f"r{self.rounds}c{index}"},
            )


class _StampRecordingRegistry:
    """A one-tool registry that keeps the stamp each invoked call arrived with."""

    def __init__(self, trust: Trust = Trust.TRUSTED) -> None:
        self.stamps: list[TurnStamp] = []
        self._trust = trust

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return [ToolSpec(name="noop", description="do nothing", parameters={})]

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.stamps.append(call.stamp)
        return ToolResult(call_id=call.id, content="ok", trust=self._trust)


async def _noop_handler(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


def _context(
    sink: RecordingAuditSink,
    *,
    budget: int | DispatchBudget,
    costs: ToolCostPolicy = UNIFORM_COST,
    salience: SaliencePolicy = REPEAT_SALIENCE,
) -> ToolLoopContext:
    """A loop context over a two-tool registry. ``budget`` is a limit, or a pool to share."""
    registry = InMemoryToolRegistry(
        {
            name: (ToolSpec(name=name, description="do nothing", parameters={}), _noop_handler)
            for name in ("noop", "big")
        }
    )
    return ToolLoopContext(
        dispatcher=ToolDispatcher(
            registry,
            sink,
            _TickingClock(),
            policy=DispatchPolicy(costs=costs, salience=salience),
        ),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        budget=DispatchBudget(budget) if isinstance(budget, int) else budget,
    )


async def _run(backend: _MultiCallBackend, context: ToolLoopContext) -> list[str | object]:
    working: list[Message] = [
        Message(role=Role.USER, text="go", at=_START, turn_id="t-1"),
    ]
    return [delta async for delta in stream_tool_loop(backend, "m", working, context)]


async def test_the_budget_is_a_total_counted_across_rounds() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=5)
    await _run(backend, _context(sink, budget=12))
    assert backend.rounds == MAX_TOOL_STEPS
    assert len(sink.records) == 5 * MAX_TOOL_STEPS
    ran = [record for record in sink.records if record.ok]
    refused = [record for record in sink.records if not record.ok]
    assert len(ran) == 12
    assert len(refused) == 5 * MAX_TOOL_STEPS - 12
    assert {record.detail for record in refused} == {BUDGET_EXHAUSTED_MSG}


async def test_the_call_at_the_boundary_runs_and_the_next_one_is_refused() -> None:
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=2), _context(sink, budget=1))
    first, second = sink.records[0], sink.records[1]
    assert (first.ok, first.detail) == (True, "ok")
    assert (second.ok, second.detail) == (False, BUDGET_EXHAUSTED_MSG)


async def test_a_zero_budget_dispatches_nothing_and_still_audits_every_refusal() -> None:
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=0))
    assert all(not record.ok for record in sink.records)
    assert len(sink.records) == 3 * MAX_TOOL_STEPS


async def test_a_refused_call_renders_no_activity_chip() -> None:
    sink = RecordingAuditSink()
    deltas = await _run(_MultiCallBackend(per_round=4), _context(sink, budget=6))
    steps = [delta for delta in deltas if isinstance(delta, ToolStep)]
    assert len(steps) == 6
    assert {step.tool_name for step in steps} == {"noop"}


async def test_every_refused_call_still_answers_its_tool_call_message() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=3)
    await _run(backend, _context(sink, budget=1))
    last = backend.seen[-1]
    called = [
        call.id for message in last for call in (message.tool_calls or ()) if message.tool_calls
    ]
    answered = [message.tool_call_id for message in last if message.role is Role.TOOL]
    assert called
    assert called == answered


async def test_an_expensive_tool_spends_its_price_not_one_call() -> None:
    sink = RecordingAuditSink()
    costs = ToolCostPolicy({"big": 3})
    await _run(_ScriptedBackend(["big", "big", "big"]), _context(sink, budget=6, costs=costs))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, True, False]
    assert first_round[2].detail == BUDGET_EXHAUSTED_MSG


async def test_a_call_that_does_not_fit_closes_the_budget_to_cheaper_calls_behind_it() -> None:
    sink = RecordingAuditSink()
    costs = ToolCostPolicy({"big": 3})
    await _run(_ScriptedBackend(["big", "big", "noop"]), _context(sink, budget=4, costs=costs))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, False, False]
    assert [record.name for record in first_round] == ["big", "big", "noop"]
    assert {record.detail for record in first_round[1:]} == {BUDGET_EXHAUSTED_MSG}


async def test_an_unpriced_tool_still_costs_exactly_one() -> None:
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=5), _context(sink, budget=3, costs=UNIFORM_COST))
    assert len([record for record in sink.records if record.ok]) == 3


def _bare_context() -> ToolLoopContext:
    """A context built without a budget, as every root caller has."""
    return ToolLoopContext(
        dispatcher=None,
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def test_the_default_budget_is_the_module_bound() -> None:
    assert _bare_context().budget.limit == MAX_TOOL_DISPATCHES


async def test_each_context_built_without_one_gets_its_own_pool() -> None:
    first, second = _bare_context(), _bare_context()
    assert first.budget.charge(MAX_TOOL_DISPATCHES) is True
    assert second.budget.spent == 0


async def test_one_pool_shared_by_two_loops_bounds_their_total_not_each_of_them() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=4)
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=pool))
    spent_by_the_first = pool.spent
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=pool))
    assert spent_by_the_first == 4
    assert pool.spent == 4
    assert len([record for record in sink.records if record.ok]) == 4


async def test_a_pool_closed_by_an_earlier_loop_stays_closed_for_a_later_one() -> None:
    pool = DispatchBudget(limit=4)
    costs = ToolCostPolicy({"big": 3})
    first = RecordingAuditSink()
    await _run(_ScriptedBackend(["big", "big"]), _context(first, budget=pool, costs=costs))
    assert (pool.spent, pool.closed) == (3, True)
    second = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=1), _context(second, budget=pool, costs=costs))
    assert [record.detail for record in second.records] == [BUDGET_EXHAUSTED_MSG] * MAX_TOOL_STEPS


async def test_the_dispatch_stamp_passes_the_pool_to_whatever_the_call_spawns() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=1)
    registry = _StampRecordingRegistry()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(registry, sink, _TickingClock()),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        budget=pool,
    )
    await _run(_MultiCallBackend(per_round=1), context)
    assert registry.stamps
    assert all(stamp.budget is pool for stamp in registry.stamps)


def _stamp_context(registry: _StampRecordingRegistry) -> ToolLoopContext:
    """A loop context over a stamp-recording registry, with a fresh ledger and pool."""
    return ToolLoopContext(
        dispatcher=ToolDispatcher(registry, RecordingAuditSink(), _TickingClock()),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def test_the_dispatch_stamp_names_the_sources_the_turn_has_read() -> None:
    registry = _StampRecordingRegistry(trust=Trust.UNTRUSTED)
    await _run(_MultiCallBackend(per_round=1), _stamp_context(registry))
    assert len(registry.stamps) == MAX_TOOL_STEPS
    assert registry.stamps[0] == TurnStamp(session_id="s", turn_id="t-1", tainted=False, sources=())
    via_noop = (Provenance(SourceKind.TOOL, "noop"),)
    assert all(stamp.sources == via_noop for stamp in registry.stamps[1:])


async def test_the_dispatch_stamp_includes_the_turns_escalation_slot() -> None:
    registry = _StampRecordingRegistry()
    slot = EscalationSlot()
    context = _stamp_context(registry)
    context = ToolLoopContext(
        dispatcher=context.dispatcher,
        clock=context.clock,
        turn_id=context.turn_id,
        taint=context.taint,
        nonce=context.nonce,
        session_id=context.session_id,
        escalation=slot,
    )
    await _run(_MultiCallBackend(per_round=1), context)
    assert registry.stamps
    assert all(stamp.escalation is slot for stamp in registry.stamps)


async def test_an_escalation_less_context_stamps_no_slot() -> None:
    registry = _StampRecordingRegistry()
    await _run(_MultiCallBackend(per_round=1), _stamp_context(registry))
    assert registry.stamps
    assert all(stamp.escalation is None for stamp in registry.stamps)


async def test_a_call_matching_no_advertised_spec_attributes_no_source() -> None:
    registry = _StampRecordingRegistry(trust=Trust.UNTRUSTED)
    context = _stamp_context(registry)
    await _run(_ScriptedBackend(["ghost", "ghost"]), context)
    assert registry.stamps
    assert context.taint.tainted is True
    assert all(stamp.sources == () for stamp in registry.stamps)


class _RepeatBackend(_MultiCallBackend):
    """Emits the same call over and over: one name and one argument set, every round."""

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
        self.rounds += 1
        self.seen.append(list(messages))
        for index in range(self._per_round):
            yield ToolCall(id=f"r{self.rounds}c{index}", name="noop", arguments={"path": "a.txt"})


async def test_an_identical_call_repeated_in_one_round_runs_once() -> None:
    sink = RecordingAuditSink()
    await _run(_RepeatBackend(per_round=3), _context(sink, budget=MAX_TOOL_DISPATCHES))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, False, False]
    assert {record.detail for record in first_round[1:]} == {REDUNDANT_MSG}


async def test_a_repeat_runs_a_second_time_but_never_a_third() -> None:
    sink = RecordingAuditSink()
    await _run(_RepeatBackend(per_round=1), _context(sink, budget=MAX_TOOL_DISPATCHES))
    assert [record.ok for record in sink.records] == [True, True] + [False] * (MAX_TOOL_STEPS - 2)
    assert {record.detail for record in sink.records[2:]} == {REDUNDANT_MSG}


async def test_a_refused_repeat_is_never_charged_to_the_budget() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=2)
    await _run(_RepeatBackend(per_round=5), _context(sink, budget=pool))
    assert (pool.spent, pool.closed) == (2, False)
    assert {record.detail for record in sink.records if not record.ok} == {REDUNDANT_MSG}


async def test_the_same_fixture_spends_the_whole_pool_with_salience_off() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=2)
    await _run(_RepeatBackend(per_round=5), _context(sink, budget=pool, salience=ALWAYS_SALIENT))
    assert (pool.spent, pool.closed) == (2, True)
    assert BUDGET_EXHAUSTED_MSG in {record.detail for record in sink.records}


async def test_a_refused_repeat_renders_no_activity_chip() -> None:
    sink = RecordingAuditSink()
    deltas = await _run(_RepeatBackend(per_round=4), _context(sink, budget=MAX_TOOL_DISPATCHES))
    chips = [delta for delta in deltas if isinstance(delta, ToolStep)]
    dispatched = [record for record in sink.records if record.ok]
    assert len(chips) == len(dispatched) == 2


async def test_every_refused_repeat_still_answers_its_tool_call_message() -> None:
    sink = RecordingAuditSink()
    backend = _RepeatBackend(per_round=3)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    last = backend.seen[-1]
    calls = [message for message in last if message.role is Role.ASSISTANT and message.tool_calls]
    answers = [message for message in last if message.role is Role.TOOL]
    assert len(answers) == sum(len(message.tool_calls) for message in calls)


async def test_a_second_loop_counts_its_repeats_against_its_own_rounds() -> None:
    first, second = RecordingAuditSink(), RecordingAuditSink()
    await _run(_RepeatBackend(per_round=1), _context(first, budget=MAX_TOOL_DISPATCHES))
    await _run(_RepeatBackend(per_round=1), _context(second, budget=MAX_TOOL_DISPATCHES))
    assert [record.ok for record in first.records].count(True) == 2
    assert [record.ok for record in second.records].count(True) == 2


# How much wider than the cap a runaway round is here: large enough that an unbounded round is
# unmistakable, small enough that eight such rounds stay fast.
_RUNAWAY = 200


def _appended_by_the_first_round(backend: _MultiCallBackend) -> int:
    """How many messages the first round added to ``working``, read from the next round."""
    return len(backend.seen[1]) - len(backend.seen[0])


async def test_a_round_wider_than_the_cap_appends_a_bounded_number_of_messages() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    assert backend.rounds == MAX_TOOL_STEPS
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 2
    assert len(sink.records) == (MAX_CALLS_PER_ROUND + 1) * MAX_TOOL_STEPS


async def test_the_calls_past_the_overflow_slot_are_dropped_rather_than_refused() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    first_round = sink.records[: MAX_CALLS_PER_ROUND + 1]
    assert len(first_round) == MAX_CALLS_PER_ROUND + 1
    assert [record.ok for record in first_round] == [True] * MAX_CALLS_PER_ROUND + [False]
    assert first_round[-1].detail == ROUND_OVERSIZED_MSG


async def test_the_model_can_tell_a_truncated_round_from_a_short_one() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    second_round_context = backend.seen[1]
    notices = [
        message
        for message in second_round_context
        if message.role is Role.TOOL and message.text == ROUND_OVERSIZED_MSG
    ]
    assert len(notices) == 1
    assert str(MAX_CALLS_PER_ROUND) in ROUND_OVERSIZED_MSG


async def test_a_truncated_round_still_answers_every_call_it_recorded() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    last = backend.seen[-1]
    called = [call.id for message in last for call in message.tool_calls]
    answered = [message.tool_call_id for message in last if message.role is Role.TOOL]
    assert called
    assert called == answered


async def test_the_overflow_slot_is_charged_nothing_and_renders_no_chip() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=1000)
    deltas = await _run(_MultiCallBackend(per_round=_RUNAWAY), _context(sink, budget=pool))
    assert pool.spent == MAX_CALLS_PER_ROUND * MAX_TOOL_STEPS
    chips = [delta for delta in deltas if isinstance(delta, ToolStep)]
    assert len(chips) == MAX_CALLS_PER_ROUND * MAX_TOOL_STEPS


async def test_two_rounds_at_the_cap_exhaust_the_default_pool() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget()
    await _run(_MultiCallBackend(per_round=_RUNAWAY), _context(sink, budget=pool))
    assert pool.spent == MAX_TOOL_DISPATCHES
    assert len([record for record in sink.records if record.ok]) == MAX_CALLS_PER_ROUND * 2


async def test_a_round_of_identical_spam_is_bounded_though_it_costs_the_pool_nothing() -> None:
    sink = RecordingAuditSink()
    pool = DispatchBudget()
    backend = _RepeatBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=pool))
    assert pool.spent == 2
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 2
    assert {record.detail for record in sink.records[1:MAX_CALLS_PER_ROUND]} == {REDUNDANT_MSG}
    assert sink.records[MAX_CALLS_PER_ROUND].detail == ROUND_OVERSIZED_MSG


async def test_a_round_at_the_cap_is_left_exactly_as_it_was() -> None:
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=MAX_CALLS_PER_ROUND)
    await _run(backend, _context(sink, budget=DispatchBudget(limit=1000)))
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 1
    assert all(record.ok for record in sink.records)
    assert ROUND_OVERSIZED_MSG not in {record.detail for record in sink.records}


class _ImageReturningRegistry:
    """A one-tool registry in place of the capture built-in: one untrusted result with an image."""

    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=1600, height=900)

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return [ToolSpec(name="capture_screen", description="look", parameters={})]

    async def invoke(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            call_id=call.id,
            content="screen capture of the primary display",
            trust=Trust.UNTRUSTED,
            images=(self.picture,),
        )


class _OneCaptureThenAnswer(_MultiCallBackend):
    """Asks for one capture in round one, then answers, keeping the messages of each round."""

    def __init__(self) -> None:
        super().__init__(per_round=1)

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
        self.rounds += 1
        self.seen.append(list(messages))
        if self.rounds == 1:
            yield ToolCall(id="c1", name="capture_screen", arguments={})
            return
        yield TextChunk("your screen shows an invoice")


async def test_a_captures_picture_reaches_the_next_rounds_context() -> None:
    sink = RecordingAuditSink()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(_ImageReturningRegistry(), sink, _TickingClock()),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        budget=DispatchBudget(MAX_TOOL_DISPATCHES),
    )
    backend = _OneCaptureThenAnswer()

    deltas = await _run(backend, context)

    assert [delta for delta in deltas if isinstance(delta, str)] == ["your screen shows an invoice"]
    second_round = backend.seen[1]
    tool_messages = [message for message in second_round if message.role is Role.TOOL]
    assert [message.images for message in tool_messages] == [(_ImageReturningRegistry.picture,)]
    assert context.taint.tainted is True


async def test_a_captures_bytes_never_reach_the_audit_line() -> None:
    sink = RecordingAuditSink()
    context = ToolLoopContext(
        dispatcher=ToolDispatcher(_ImageReturningRegistry(), sink, _TickingClock()),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        budget=DispatchBudget(MAX_TOOL_DISPATCHES),
    )
    await _run(_OneCaptureThenAnswer(), context)

    assert [record.detail for record in sink.records] == ["screen capture of the primary display"]
    assert b"\x89PNG" not in b"".join(record.detail.encode() for record in sink.records)


class _CadencedBackend:
    """Streams a reply and ends it with the server's decode rate, once per round."""

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
        yield TextChunk("answer")
        yield DecodeCadence(tokens_per_second=17.29, tokens=96)


async def test_a_cadence_reaches_a_watching_caller_and_never_the_stream() -> None:
    watch = CadenceWatch(22.0)
    context = _context(RecordingAuditSink(), budget=4)
    context = replace(context, cadence=watch)
    yielded = [event async for event in stream_tool_loop(_CadencedBackend(), "m", [], context)]
    assert yielded == ["answer"]
    reading = watch.reading()
    assert reading is not None
    assert reading.observed.tokens_per_second == 17.29


async def test_a_caller_with_no_watch_drops_the_cadence_and_keeps_streaming() -> None:
    context = _context(RecordingAuditSink(), budget=4)
    assert context.cadence is None
    yielded = [event async for event in stream_tool_loop(_CadencedBackend(), "m", [], context)]
    assert yielded == ["answer"]


class _StoppingBackend:
    """Streams a reply and ends it with the server's stop reason, once per round."""

    def __init__(self, reason: StopReason) -> None:
        self._reason = reason

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
        yield TextChunk("answer")
        yield DecodeStop(self._reason)


async def test_a_stop_reaches_a_ledger_keeping_caller_and_never_the_stream() -> None:
    ledger = StopLedger()
    context = replace(_context(RecordingAuditSink(), budget=4), stops=ledger)
    backend = _StoppingBackend(StopReason.CAPPED)
    yielded = [event async for event in stream_tool_loop(backend, "m", [], context)]
    assert yielded == ["answer"]
    assert ledger.capped


async def test_a_caller_with_no_ledger_drops_the_stop_and_keeps_streaming() -> None:
    context = _context(RecordingAuditSink(), budget=4)
    assert context.stops is None
    backend = _StoppingBackend(StopReason.FINISHED)
    yielded = [event async for event in stream_tool_loop(backend, "m", [], context)]
    assert yielded == ["answer"]
