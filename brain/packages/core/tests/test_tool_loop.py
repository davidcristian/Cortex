"""Behavior tests for the tool loop's bounds: the dispatch budget, salience, and the round cap.

``MAX_TOOL_STEPS`` bounds inference *rounds*; within one round the loop used to dispatch every
call the model emitted, uncapped, on the only path that reaches external services. These tests
drive ``stream_tool_loop`` directly (the engine and each subagent share it) so the budget can be
set small and its exact boundary asserted. The rest of the loop's behavior is covered through
the engine in ``test_engine.py``, and the round cap's pure arithmetic in ``test_tool_round.py``.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    ALWAYS_SALIENT,
    BUDGET_EXHAUSTED_MSG,
    MAX_CALLS_PER_ROUND,
    REDUNDANT_MSG,
    REPEAT_SALIENCE,
    ROUND_OVERSIZED_MSG,
    DispatchPolicy,
    EscalationSlot,
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
    """Deterministic clock: each now() is one second after the previous one."""

    def __init__(self) -> None:
        self._ticks = 0

    def now(self) -> datetime:
        at = _START + timedelta(seconds=self._ticks)
        self._ticks += 1
        return at


class _MultiCallBackend:
    """Emits ``per_round`` tool calls every inference step and never a final answer.

    The shape a budget has to survive: one round can carry an unbounded number of calls, so a
    round count alone bounds nothing about how much of the outside world a turn touches.
    """

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
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.rounds += 1
        self.seen.append(list(messages))
        yield TextChunk("working ")
        for index in range(self._per_round):
            yield ToolCall(
                id=f"r{self.rounds}c{index}",
                name="noop",
                # Distinct per call and per round, so these budget fixtures exercise the
                # budget alone: an identical repeat would be refused by the default salience
                # policy first and never reach the pool (ADR-0009 salience addendum).
                arguments={"call": f"r{self.rounds}c{index}"},
            )


class _ScriptedBackend(_MultiCallBackend):
    """Emits a fixed sequence of tool *names* every round, so a round can mix prices."""

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
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.rounds += 1
        self.seen.append(list(messages))
        for index, name in enumerate(self._names):
            yield ToolCall(
                id=f"r{self.rounds}c{index}",
                name=name,
                arguments={"call": f"r{self.rounds}c{index}"},
            )


class _StampRecordingRegistry:
    """A one-tool registry that keeps the stamp each invoked call arrived carrying.

    ``trust`` is what every result comes back as: ``UNTRUSTED`` makes it stand in for a tool
    that reads external content, which is what taints the turn and gives it a source.
    """

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
    """A loop context over a two-tool registry; ``budget`` is a limit, or a pool to share."""
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
    # Five calls a round over the full eight rounds is forty attempted dispatches; the budget
    # is a total, so twelve run and the other twenty eight are refused. A per-round cap would
    # instead have let MAX_TOOL_STEPS multiply it back up.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=5)
    await _run(backend, _context(sink, budget=12))
    assert backend.rounds == MAX_TOOL_STEPS  # the round bound still applies, independently
    assert len(sink.records) == 5 * MAX_TOOL_STEPS  # every attempt audited, refusals included
    ran = [record for record in sink.records if record.ok]
    refused = [record for record in sink.records if not record.ok]
    assert len(ran) == 12
    assert len(refused) == 5 * MAX_TOOL_STEPS - 12
    assert {record.detail for record in refused} == {BUDGET_EXHAUSTED_MSG}


async def test_the_call_at_the_boundary_runs_and_the_next_one_is_refused() -> None:
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=2), _context(sink, budget=1))
    first, second = sink.records[0], sink.records[1]
    assert (first.ok, first.detail) == (True, "ok")  # the last call inside the budget runs
    assert (second.ok, second.detail) == (False, BUDGET_EXHAUSTED_MSG)


async def test_a_zero_budget_dispatches_nothing_and_still_audits_every_refusal() -> None:
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=0))
    assert all(not record.ok for record in sink.records)
    assert len(sink.records) == 3 * MAX_TOOL_STEPS


async def test_a_refused_call_renders_no_activity_chip() -> None:
    # The guard sits above the ToolStep yield, so a chip keeps meaning "a tool is running now"
    # (ADR-0009 budget addendum decision 4). This is also what finally makes chip emission
    # bounded per turn, which the chip addendum had claimed of MAX_TOOL_STEPS alone.
    sink = RecordingAuditSink()
    deltas = await _run(_MultiCallBackend(per_round=4), _context(sink, budget=6))
    steps = [delta for delta in deltas if isinstance(delta, ToolStep)]
    assert len(steps) == 6  # one per dispatch that actually ran, none for the refusals
    assert {step.tool_name for step in steps} == {"noop"}


async def test_every_refused_call_still_answers_its_tool_call_message() -> None:
    # Why a refusal is dispatched rather than skipped: an OpenAI-compatible backend requires one
    # Role.TOOL message per tool_call_id, so breaking out of the loop mid-round would send the
    # next round a malformed conversation. Assert the shape the backend actually receives.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=3)
    await _run(backend, _context(sink, budget=1))
    last = backend.seen[-1]  # the most complete context any round was given
    called = [
        call.id for message in last for call in (message.tool_calls or ()) if message.tool_calls
    ]
    answered = [message.tool_call_id for message in last if message.role is Role.TOOL]
    assert called  # the round did emit calls, so the assertion below is not vacuous
    assert called == answered  # every call answered exactly once, in order


async def test_an_expensive_tool_spends_its_price_not_one_call() -> None:
    # The point of prices (ADR-0009 cost addendum): with a flat count all three calls fit in
    # a budget of six, because three is less than six. Charged at three apiece, two fit.
    sink = RecordingAuditSink()
    costs = ToolCostPolicy({"big": 3})
    await _run(_ScriptedBackend(["big", "big", "big"]), _context(sink, budget=6, costs=costs))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, True, False]
    assert first_round[2].detail == BUDGET_EXHAUSTED_MSG


async def test_a_call_that_does_not_fit_closes_the_budget_to_cheaper_calls_behind_it() -> None:
    # The deliberate choice: the refusal tells the model to stop calling tools entirely, so
    # letting a one-cost call through after a three-cost one was refused would make that
    # instruction a lie, and would make the turn's spend depend on the order the model
    # happened to emit its calls in. The trailing `noop` would have fit (3 + 1 <= 4).
    sink = RecordingAuditSink()
    costs = ToolCostPolicy({"big": 3})
    await _run(_ScriptedBackend(["big", "big", "noop"]), _context(sink, budget=4, costs=costs))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, False, False]
    assert [record.name for record in first_round] == ["big", "big", "noop"]
    assert {record.detail for record in first_round[1:]} == {BUDGET_EXHAUSTED_MSG}


async def test_an_unpriced_tool_still_costs_exactly_one() -> None:
    # The compatibility property: with no tool priced, the budget is the call count it was.
    sink = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=5), _context(sink, budget=3, costs=UNIFORM_COST))
    assert len([record for record in sink.records if record.ok]) == 3


def _bare_context() -> ToolLoopContext:
    """A context built without a budget, the shape every root caller uses."""
    return ToolLoopContext(
        dispatcher=None,
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )


async def test_the_default_budget_is_the_module_bound() -> None:
    # A context built without a budget gets MAX_TOOL_DISPATCHES, so a root caller (the engine,
    # a subagent run with no spawning turn) is bounded rather than silently unlimited.
    assert _bare_context().budget.limit == MAX_TOOL_DISPATCHES


async def test_each_context_built_without_one_gets_its_own_pool() -> None:
    # The default has to be a factory, not one shared instance: a module-level default would
    # make every turn in the process spend from the same pool, so the first busy turn after a
    # restart would starve every turn after it, permanently.
    first, second = _bare_context(), _bare_context()
    assert first.budget.charge(MAX_TOOL_DISPATCHES) is True
    assert second.budget.spent == 0


async def test_one_pool_shared_by_two_loops_bounds_their_total_not_each_of_them() -> None:
    # The turn-wide property (ADR-0009 turn-wide addendum), at the seam it is built on: the
    # budget outlives one stream_tool_loop invocation, so a second loop handed the same pool
    # starts where the first stopped. Per invocation, these two loops would have run six
    # dispatches; sharing, they run four.
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=4)
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=pool))
    spent_by_the_first = pool.spent
    await _run(_MultiCallBackend(per_round=3), _context(sink, budget=pool))
    assert spent_by_the_first == 4  # the first loop alone could exhaust the shared pool
    assert pool.spent == 4  # and the second one dispatched nothing on top
    assert len([record for record in sink.records if record.ok]) == 4


async def test_a_pool_closed_by_an_earlier_loop_stays_closed_for_a_later_one() -> None:
    # Closure travels with the pool, so the second loop is refused from its very first call
    # even though a cheap call would have fit in the unspent unit.
    pool = DispatchBudget(limit=4)
    costs = ToolCostPolicy({"big": 3})
    first = RecordingAuditSink()
    await _run(_ScriptedBackend(["big", "big"]), _context(first, budget=pool, costs=costs))
    assert (pool.spent, pool.closed) == (3, True)
    second = RecordingAuditSink()
    await _run(_MultiCallBackend(per_round=1), _context(second, budget=pool, costs=costs))
    assert [record.detail for record in second.records] == [BUDGET_EXHAUSTED_MSG] * MAX_TOOL_STEPS


async def test_the_dispatch_stamp_carries_the_pool_to_whatever_the_call_spawns() -> None:
    # How a subagent reaches the turn's pool at all: the loop stamps it onto the call, the
    # dispatcher overwrites the model's stamp with that one, and the built-in reads it off the
    # call it is invoked with (spawn_subagents does exactly this in test_spawn.py).
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
    assert registry.stamps  # the tool was reached, so the assertion below is not vacuous
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


async def test_the_dispatch_stamp_carries_the_sources_the_turn_has_read() -> None:
    # The structured provenance behind the taint bit (ADR-0027 addendum), as live as the bit: the
    # first dispatch has read nothing, and every later one carries the tool the content came
    # through, named by the registry's advertisement rather than by the model's call string.
    registry = _StampRecordingRegistry(trust=Trust.UNTRUSTED)
    await _run(_MultiCallBackend(per_round=1), _stamp_context(registry))
    assert len(registry.stamps) == MAX_TOOL_STEPS
    assert registry.stamps[0] == TurnStamp(session_id="s", tainted=False, sources=())
    via_noop = (Provenance(SourceKind.TOOL, "noop"),)
    assert all(stamp.sources == via_noop for stamp in registry.stamps[1:])


async def test_the_dispatch_stamp_carries_the_turns_escalation_slot() -> None:
    # How the escalate built-in reaches the turn's handoff slot at all (ADR-0030 decision 2):
    # exactly the budget/progress path. The loop stamps `context.escalation` onto every
    # dispatch, so the one shared tool reads it per call and never holds it as state.
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
    assert registry.stamps  # the tool was reached, so the assertion below is not vacuous
    assert all(stamp.escalation is slot for stamp in registry.stamps)


async def test_an_escalation_less_context_stamps_no_slot() -> None:
    # The default is None end to end: a subagent's inner loop and every escalation-less caller
    # dispatch with no slot, which is what makes the escalate tool refuse honestly there.
    registry = _StampRecordingRegistry()
    await _run(_MultiCallBackend(per_round=1), _stamp_context(registry))
    assert registry.stamps
    assert all(stamp.escalation is None for stamp in registry.stamps)


async def test_a_call_matching_no_advertised_spec_attributes_no_source() -> None:
    # A name no advertisement snapshot carried (a hallucination, or a tool skip mode hid) can still
    # reach a live registry. It taints the turn like any untrusted read, but it names no source:
    # the fallback would be the model's own string, which is exactly what must never be stored.
    registry = _StampRecordingRegistry(trust=Trust.UNTRUSTED)
    context = _stamp_context(registry)
    await _run(_ScriptedBackend(["ghost", "ghost"]), context)
    assert registry.stamps  # the hidden tool really was invoked
    assert context.taint.tainted is True
    assert all(stamp.sources == () for stamp in registry.stamps)


class _RepeatBackend(_MultiCallBackend):
    """Emits the *same* call over and over: one name, one argument set, every round.

    The runaway shape salience exists for. The budget cannot tell this apart from a turn doing
    real work, because every one of these is a well-formed call to an advertised tool.
    """

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.rounds += 1
        self.seen.append(list(messages))
        for index in range(self._per_round):
            yield ToolCall(id=f"r{self.rounds}c{index}", name="noop", arguments={"path": "a.txt"})


async def test_an_identical_call_repeated_in_one_round_runs_once() -> None:
    # The absolute clause: the model chose all three before seeing any result, so the second and
    # third cannot inform anything the first did not.
    sink = RecordingAuditSink()
    await _run(_RepeatBackend(per_round=3), _context(sink, budget=MAX_TOOL_DISPATCHES))
    first_round = sink.records[:3]
    assert [record.ok for record in first_round] == [True, False, False]
    assert {record.detail for record in first_round[1:]} == {REDUNDANT_MSG}


async def test_a_repeat_runs_a_second_time_but_never_a_third() -> None:
    # The cap, not a prohibition: one repeat is legitimate (a retry, or a re-read of something
    # the turn changed), and the third identical attempt is the model spinning.
    sink = RecordingAuditSink()
    await _run(_RepeatBackend(per_round=1), _context(sink, budget=MAX_TOOL_DISPATCHES))
    assert [record.ok for record in sink.records] == [True, True] + [False] * (MAX_TOOL_STEPS - 2)
    assert {record.detail for record in sink.records[2:]} == {REDUNDANT_MSG}


async def test_a_refused_repeat_is_never_charged_to_the_budget() -> None:
    # The ordering that makes the policy worth having: salience is asked before the pool is
    # charged, so the turn's reach is spent on calls that reach something. Five repeats a round
    # over eight rounds is forty attempts, and this whole loop costs two.
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=2)
    await _run(_RepeatBackend(per_round=5), _context(sink, budget=pool))
    assert (pool.spent, pool.closed) == (2, False)
    assert {record.detail for record in sink.records if not record.ok} == {REDUNDANT_MSG}


async def test_the_same_fixture_spends_the_whole_pool_with_salience_off() -> None:
    # The counterfactual for the test above, and the off switch's contract: CORTEX_TOOLS_SALIENCE
    # =off is the pre-policy loop exactly, where those forty repeats do reach the pool and close
    # it. Without this pair the saving above could be an artifact of the fixture.
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=2)
    await _run(_RepeatBackend(per_round=5), _context(sink, budget=pool, salience=ALWAYS_SALIENT))
    assert (pool.spent, pool.closed) == (2, True)
    assert BUDGET_EXHAUSTED_MSG in {record.detail for record in sink.records}


async def test_a_refused_repeat_renders_no_activity_chip() -> None:
    # A chip means a tool is running now, so the salience guard sits above the ToolStep yield
    # exactly as the budget guard does.
    sink = RecordingAuditSink()
    deltas = await _run(_RepeatBackend(per_round=4), _context(sink, budget=MAX_TOOL_DISPATCHES))
    chips = [delta for delta in deltas if isinstance(delta, ToolStep)]
    dispatched = [record for record in sink.records if record.ok]
    assert len(chips) == len(dispatched) == 2


async def test_every_refused_repeat_still_answers_its_tool_call_message() -> None:
    # Refusing by dropping the call would strand this round's tool_calls without their Role.TOOL
    # answers, so re-inference would send a malformed conversation.
    sink = RecordingAuditSink()
    backend = _RepeatBackend(per_round=3)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    last = backend.seen[-1]
    calls = [message for message in last if message.role is Role.ASSISTANT and message.tool_calls]
    answers = [message for message in last if message.role is Role.TOOL]
    assert len(answers) == sum(len(message.tool_calls) for message in calls)


async def test_a_second_loop_counts_its_repeats_against_its_own_rounds() -> None:
    # Per loop, not per turn, unlike the shared budget pool: a subagent holds a different message
    # list, so a sibling's result is not an answer it can read, and refusing its read on the
    # strength of one it cannot see would deny it information rather than save a dispatch. The
    # policy object is shared by both loops here, so only the per-loop history makes this pass.
    first, second = RecordingAuditSink(), RecordingAuditSink()
    await _run(_RepeatBackend(per_round=1), _context(first, budget=MAX_TOOL_DISPATCHES))
    await _run(_RepeatBackend(per_round=1), _context(second, budget=MAX_TOOL_DISPATCHES))
    assert [record.ok for record in first.records].count(True) == 2
    assert [record.ok for record in second.records].count(True) == 2


# How much wider than the cap a runaway round is in these fixtures. Large enough that the
# unbounded shape is unmistakable, small enough that eight rounds of it stay a fast test.
_RUNAWAY = 200


def _appended_by_the_first_round(backend: _MultiCallBackend) -> int:
    """How many messages the first round added to `working`, read off the next round's context."""
    return len(backend.seen[1]) - len(backend.seen[0])


async def test_a_round_wider_than_the_cap_appends_a_bounded_number_of_messages() -> None:
    # The shape neither the pool nor salience closes (ADR-0009 round-cap addendum). Every call a
    # round emits costs an appended Role.TOOL message whether it runs or is refused, so before
    # the cap a round of 200 was 201 messages fed straight back into the next inference, and
    # eight such rounds were 1608. Now the round's whole footprint is a number: the assistant
    # message, the cap's worth of results, and the one refusal that says the rest were dropped.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    assert backend.rounds == MAX_TOOL_STEPS  # the round bound still applies, independently
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 2
    assert len(sink.records) == (MAX_CALLS_PER_ROUND + 1) * MAX_TOOL_STEPS


async def test_the_calls_past_the_overflow_slot_are_dropped_rather_than_refused() -> None:
    # Why refusing each excess call would have bounded nothing: the refusal is appended too, so
    # 200 refusals grow the context exactly as much as 200 results. The dropped calls leave no
    # trace at all, which is only sound because the one slot that is kept says so.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    first_round = sink.records[: MAX_CALLS_PER_ROUND + 1]
    assert len(first_round) == MAX_CALLS_PER_ROUND + 1  # not 200: the rest never reached dispatch
    assert [record.ok for record in first_round] == [True] * MAX_CALLS_PER_ROUND + [False]
    assert first_round[-1].detail == ROUND_OVERSIZED_MSG


async def test_the_model_can_tell_a_truncated_round_from_a_short_one() -> None:
    # A truncation the model cannot observe is the failure mode a cap must not create: it would
    # re-emit the dropped calls every round, believing they were never asked, until the round
    # bound ran out. So the kept slot's refusal names the cap and invites the next reply.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    second_round_context = backend.seen[1]
    notices = [
        message
        for message in second_round_context
        if message.role is Role.TOOL and message.text == ROUND_OVERSIZED_MSG
    ]
    assert len(notices) == 1  # exactly one notice, not one per dropped call
    assert str(MAX_CALLS_PER_ROUND) in ROUND_OVERSIZED_MSG


async def test_a_truncated_round_still_answers_every_call_it_recorded() -> None:
    # The well-formedness the budget addendum's refusals exist to preserve, now that the round's
    # assistant message is truncated as well: an OpenAI-compatible backend requires one
    # Role.TOOL message per tool_call_id, so dropping a call means dropping it from there too.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=MAX_TOOL_DISPATCHES))
    last = backend.seen[-1]
    called = [call.id for message in last for call in message.tool_calls]
    answered = [message.tool_call_id for message in last if message.role is Role.TOOL]
    assert called  # the round did record calls, so the assertion below is not vacuous
    assert called == answered


async def test_the_overflow_slot_is_charged_nothing_and_renders_no_chip() -> None:
    # It reaches nothing, so it is refused ahead of both other bounds: charging it would spend
    # the turn's reach on the model's own overproduction, and a chip means a tool is running now.
    # Eight rounds of the cap is 128, not 136, which is the whole assertion.
    sink = RecordingAuditSink()
    pool = DispatchBudget(limit=1000)
    deltas = await _run(_MultiCallBackend(per_round=_RUNAWAY), _context(sink, budget=pool))
    assert pool.spent == MAX_CALLS_PER_ROUND * MAX_TOOL_STEPS
    chips = [delta for delta in deltas if isinstance(delta, ToolStep)]
    assert len(chips) == MAX_CALLS_PER_ROUND * MAX_TOOL_STEPS


async def test_two_rounds_at_the_cap_exhaust_the_default_pool() -> None:
    # Why the cap is half of MAX_TOOL_DISPATCHES: a model chooses a round's calls before seeing
    # any of that round's results, so a blind burst that could spend the turn's whole reach is
    # strictly worse than one that must stop and read halfway.
    sink = RecordingAuditSink()
    pool = DispatchBudget()
    await _run(_MultiCallBackend(per_round=_RUNAWAY), _context(sink, budget=pool))
    assert pool.spent == MAX_TOOL_DISPATCHES
    assert len([record for record in sink.records if record.ok]) == MAX_CALLS_PER_ROUND * 2


async def test_a_round_of_identical_spam_is_bounded_though_it_costs_the_pool_nothing() -> None:
    # The case that decides what "distinct" had to mean here. Salience refuses every twin in a
    # round absolutely, so 200 identical calls reach the outside world once and spend one unit:
    # the pool is untouched and the reach bound is intact, and the context still grew by 201
    # messages of refusal. Growth is driven by calls emitted, distinct or not, so the cap counts
    # emitted calls and needs no notion of argument identity at all.
    sink = RecordingAuditSink()
    pool = DispatchBudget()
    backend = _RepeatBackend(per_round=_RUNAWAY)
    await _run(backend, _context(sink, budget=pool))
    assert pool.spent == 2  # the whole eight-round loop reached a tool exactly twice
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 2
    assert {record.detail for record in sink.records[1:MAX_CALLS_PER_ROUND]} == {REDUNDANT_MSG}
    assert sink.records[MAX_CALLS_PER_ROUND].detail == ROUND_OVERSIZED_MSG


async def test_a_round_at_the_cap_is_left_exactly_as_it_was() -> None:
    # The counterfactual for the fixtures above: the same loop one call narrower dispatches every
    # call it emitted, appends no notice, and is indistinguishable from the pre-cap loop. Without
    # this the bound could be refusing a round it should have let through.
    sink = RecordingAuditSink()
    backend = _MultiCallBackend(per_round=MAX_CALLS_PER_ROUND)
    await _run(backend, _context(sink, budget=DispatchBudget(limit=1000)))
    assert _appended_by_the_first_round(backend) == MAX_CALLS_PER_ROUND + 1
    assert all(record.ok for record in sink.records)
    assert ROUND_OVERSIZED_MSG not in {record.detail for record in sink.records}


class _ImageReturningRegistry:
    """A one-tool registry standing in for the capture built-in: one untrusted result with a
    picture on it, in the shape the real tool returns."""

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
    """Asks for one capture in round one, then answers, recording the message list each round.

    This is what makes the picture's whole journey observable: the loop re-sends ``working``
    every round, so round two's list is where the image has to still be.
    """

    def __init__(self) -> None:
        super().__init__(per_round=1)

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, tools, schema
        self.rounds += 1
        self.seen.append(list(messages))
        if self.rounds == 1:
            yield ToolCall(id="c1", name="capture_screen", arguments={})
            return
        yield TextChunk("your screen shows an invoice")


async def test_a_captures_picture_reaches_the_next_rounds_context() -> None:
    """End to end through the loop: the picture a tool returned is on the TOOL message the
    second inference round is given. The loop re-sends the whole working list every round, so
    this is also what lets an image from round one still be there in round three."""
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
    # And the turn is tainted by the very value that carried the pixels.
    assert context.taint.tainted is True


async def test_a_captures_bytes_never_reach_the_audit_line() -> None:
    """The audit sink logs ``result.content`` verbatim, so pixels riding beside it (rather than
    inside it) is what keeps megabytes out of the trail on every path."""
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
