"""Behavior tests for the tool loop's dispatch budget (ADR-0009 budget addendum).

``MAX_TOOL_STEPS`` bounds inference *rounds*; within one round the loop used to dispatch every
call the model emitted, uncapped, on the only path that reaches external services. These tests
drive ``stream_tool_loop`` directly (the engine and each subagent share it) so the budget can be
set small and its exact boundary asserted. The rest of the loop's behavior is covered through
the engine in ``test_engine.py``.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

from cortex_core import (
    ALWAYS_SALIENT,
    BUDGET_EXHAUSTED_MSG,
    REDUNDANT_MSG,
    REPEAT_SALIENCE,
    DispatchPolicy,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    SaliencePolicy,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.tool_budget import (
    MAX_TOOL_DISPATCHES,
    UNIFORM_COST,
    DispatchBudget,
    ToolCostPolicy,
)
from cortex_core.tool_loop import MAX_TOOL_STEPS, ToolLoopContext, ToolStep, stream_tool_loop

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
    """A one-tool registry that keeps the stamp each invoked call arrived carrying."""

    def __init__(self) -> None:
        self.stamps: list[TurnStamp] = []

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return [ToolSpec(name="noop", description="do nothing", parameters={})]

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.stamps.append(call.stamp)
        return ToolResult(call_id=call.id, content="ok", trust=Trust.TRUSTED)


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
