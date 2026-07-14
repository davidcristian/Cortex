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
    BUDGET_EXHAUSTED_MSG,
    InferenceEvent,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    RecordingAuditSink,
    Role,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
)
from cortex_core.tool_budget import MAX_TOOL_DISPATCHES, UNIFORM_COST, ToolCostPolicy
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
            yield ToolCall(id=f"r{self.rounds}c{index}", name="noop", arguments={})


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
            yield ToolCall(id=f"r{self.rounds}c{index}", name=name, arguments={})


async def _noop_handler(arguments: Mapping[str, object]) -> str:
    del arguments
    return "ok"


def _context(
    sink: RecordingAuditSink, *, budget: int, costs: ToolCostPolicy = UNIFORM_COST
) -> ToolLoopContext:
    registry = InMemoryToolRegistry(
        {
            name: (ToolSpec(name=name, description="do nothing", parameters={}), _noop_handler)
            for name in ("noop", "big")
        }
    )
    return ToolLoopContext(
        dispatcher=ToolDispatcher(registry, sink, _TickingClock(), costs=costs),
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
        dispatch_budget=budget,
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


async def test_the_default_budget_is_the_module_bound() -> None:
    # A context built without a budget gets MAX_TOOL_DISPATCHES, so the engine and each
    # subagent (neither passes one) are bounded rather than silently unlimited.
    context = ToolLoopContext(
        dispatcher=None,
        clock=_TickingClock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="n",
        session_id="s",
    )
    assert context.dispatch_budget == MAX_TOOL_DISPATCHES
