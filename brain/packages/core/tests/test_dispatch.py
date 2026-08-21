"""Behavior tests for ToolDispatcher: run one call, and audit every outcome.

The dispatcher's contract is that no dispatch is ever unaudited and a failure never
crashes the loop. A registry error comes back as an ``is_error`` result the model reads.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

from cortex_core import (
    ALWAYS_SALIENT,
    BUDGET_EXHAUSTED_MSG,
    DENIED_MSG,
    REDUNDANT_MSG,
    USER_DECLINED_MSG,
    DispatchPolicy,
    DispatchRefusal,
    InMemoryToolRegistry,
    RecordingAuditSink,
    RecordingConfirmer,
    ToolCall,
    ToolCostPolicy,
    ToolDispatcher,
    ToolError,
    ToolResult,
    ToolSpec,
    Trust,
    TurnStamp,
)
from cortex_core.tool_budget import DEFAULT_TOOL_COST

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    """Clock pinned to a single instant, so audit timestamps are assertable."""

    def now(self) -> datetime:
        return _AT


def _spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=name, parameters={"type": "object"})


async def _ran(arguments: Mapping[str, object]) -> str:
    return f"ran:{arguments['path']}"


def _outbound(sink: RecordingAuditSink, confirmer: RecordingConfirmer | None) -> ToolDispatcher:
    """A dispatcher over a spy 'send' tool that records whether it ran."""
    return ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        sink,
        _FixedClock(),
        confirmer=confirmer,
    )


async def _boom(arguments: Mapping[str, object]) -> str:
    del arguments
    msg = "tool blew up"
    raise ToolError(msg)


def _dispatcher(registry: InMemoryToolRegistry, sink: RecordingAuditSink) -> ToolDispatcher:
    return ToolDispatcher(registry, sink, _FixedClock())


async def test_successful_call_returns_the_result_and_audits_ok() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    result = await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c-1", name="read", arguments={"path": "/etc/hosts"})
    )
    assert result == ToolResult(call_id="c-1", content="ran:/etc/hosts", is_error=False)
    (record,) = sink.records
    assert (record.name, record.ok, record.detail, record.at) == (
        "read",
        True,
        "ran:/etc/hosts",
        _AT,
    )
    assert record.arguments == {"path": "/etc/hosts"}


async def test_unknown_tool_becomes_an_error_result_and_is_audited() -> None:
    sink = RecordingAuditSink()
    result = await _dispatcher(InMemoryToolRegistry({}), sink).dispatch(
        ToolCall(id="c-2", name="missing", arguments={})
    )
    assert result.call_id == "c-2"
    assert result.is_error is True
    assert "missing" in result.content
    (record,) = sink.records
    assert record.ok is False
    assert "missing" in record.detail


async def test_tool_failure_becomes_a_trusted_error_result_and_is_audited() -> None:
    # A dispatch error is our own message, not external content (ADR-0013): trusted, so it
    # neither frames as data nor taints the turn.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _boom)})
    result = await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c-3", name="read", arguments={})
    )
    assert result == ToolResult(
        call_id="c-3", content="tool blew up", is_error=True, trust=Trust.TRUSTED
    )
    (record,) = sink.records
    assert (record.ok, record.detail, record.trust) == (False, "tool blew up", Trust.TRUSTED)


async def test_audit_records_the_result_provenance() -> None:
    # The in-memory registry is the remote (untrusted) twin, so its results are UNTRUSTED.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"})
    )
    (record,) = sink.records
    assert record.trust is Trust.UNTRUSTED


async def test_gated_tool_on_a_tainted_turn_is_blocked_without_a_confirmer() -> None:
    # The taint block (ADR-0022 decision 2): after untrusted content, the outbound surface
    # is closed for the turn. The call is denied and never run, with or without a confirmer.
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG
    assert result.trust is Trust.TRUSTED  # the block is our own message, not external content
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, DENIED_MSG)


async def test_gated_tool_on_a_tainted_turn_is_blocked_even_when_a_confirmer_would_approve() -> (
    None
):
    # A send demanded by injected content is never merely a confirm-away (ADR-0022): the
    # confirmer is deliberately not consulted on a tainted turn. An approver changes nothing.
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
    )
    assert result.content == DENIED_MSG
    assert confirmer.requests == ()  # never consulted


async def test_gated_tool_on_a_clean_turn_runs_when_the_user_approves() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    assert result.content == "ran:/p"  # the tool ran
    (request,) = confirmer.requests
    assert request.tool_name == "send"
    assert request.arguments == {"path": "/p"}  # the draft the user approved
    assert "approval" in request.reason


async def test_gated_tool_on_a_clean_turn_is_declined_when_the_user_says_no() -> None:
    sink = RecordingAuditSink()
    confirmer = RecordingConfirmer(answer=False)
    result = await _outbound(sink, confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG  # "the user said no", not the taint block
    assert result.trust is Trust.TRUSTED
    assert confirmer.requests != ()  # it was asked, and said no
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, USER_DECLINED_MSG)


async def test_gated_tool_on_a_clean_turn_is_declined_without_a_confirmer() -> None:
    # Fail-closed (ADR-0022): every gated call needs the human's approval. A deployment
    # with no confirmer wired cannot perform the action, tainted or not.
    result = await _outbound(RecordingAuditSink(), None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    assert result.content == USER_DECLINED_MSG


async def test_ungated_tool_on_a_tainted_turn_runs_without_confirmation() -> None:
    confirmer = RecordingConfirmer(answer=False)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=False,
    )
    assert result.content == "ran:/p"
    assert confirmer.requests == ()


async def test_describe_tools_passes_through_to_the_registry() -> None:
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran), "list": (_spec("list"), _ran)})
    specs = await _dispatcher(registry, RecordingAuditSink()).describe_tools()
    assert [spec.name for spec in specs] == ["read", "list"]


class _CallRecordingRegistry:
    """A registry that records the exact ToolCall values it was invoked with (ADR-0018)."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    async def describe_tools(self) -> list[ToolSpec]:
        return []

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        return ToolResult(call_id=call.id, content="ok", trust=Trust.TRUSTED)


async def test_dispatch_stamps_the_turns_provenance_onto_the_invoked_call() -> None:
    # Built-ins that spawn further work read the stamp (ADR-0018/0027); the registry sees
    # the turn's taint and origin session, not the default the call was constructed with.
    registry = _CallRecordingRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="c", name="spawn", arguments={}),
        stamp=TurnStamp(session_id="s-1", tainted=True),
    )
    (stamped,) = registry.calls
    assert stamped.stamp == TurnStamp(session_id="s-1", tainted=True)
    assert (stamped.id, stamped.name) == ("c", "spawn")  # everything else rides unchanged


async def test_dispatch_overwrites_a_forged_stamp_with_the_turns() -> None:
    # The stamp is never the model's to set: a call arriving pre-marked tainted (or claiming
    # another session) on a clean turn is overwritten, so a forged stamp feeds nothing.
    registry = _CallRecordingRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    forged = TurnStamp(session_id="not-mine", tainted=True)
    await dispatcher.dispatch(
        ToolCall(id="c", name="spawn", arguments={}, stamp=forged),
        stamp=TurnStamp(session_id="s-2", tainted=False),
    )
    (stamped,) = registry.calls
    assert stamped.stamp == TurnStamp(session_id="s-2", tainted=False)


async def test_dispatch_without_a_stamp_leaves_the_call_unattributed() -> None:
    # The UNSTAMPED default (ADR-0027): no session, no taint, matching the old
    # tainted=False posture. A forged stamp is still discarded.
    registry = _CallRecordingRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="c", name="spawn", arguments={}, stamp=TurnStamp(tainted=True))
    )
    (stamped,) = registry.calls
    assert stamped.stamp == TurnStamp(session_id="", tainted=False)


async def test_gated_names_gate_a_call_the_snapshot_advertised_as_ungated() -> None:
    # The authoritative backstop (ADR-0022): a flaky sidecar can hide a gated tool from the
    # turn's advertisement snapshot (skip mode), so the loop may pass gated=False; the
    # dispatcher's own gated-name set still gates it. On a clean turn, that means confirm.
    sink = RecordingAuditSink()
    confirmer = RecordingConfirmer(answer=False)
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        sink,
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gated_names={"send"}),
    )
    result = await dispatcher.dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=False,
    )
    assert result.content == USER_DECLINED_MSG  # gated by name, and the user declined
    assert confirmer.requests != ()


async def test_gated_names_deny_a_tainted_call_the_snapshot_advertised_as_ungated() -> None:
    # Same window on a tainted turn: the dispatcher's authoritative set denies outright,
    # the confirmer never consulted. There is no gate bypass even if advertisement missed the tool.
    confirmer = RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gated_names={"send"}),
    )
    result = await dispatcher.dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=False,
    )
    assert result.content == DENIED_MSG
    assert confirmer.requests == ()  # never consulted


async def test_a_name_outside_the_gated_set_stays_ungated() -> None:
    # The set only gates its own names. An ordinary tool still runs untouched.
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"read": (_spec("read"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        policy=DispatchPolicy(gated_names={"send"}),
    )
    result = await dispatcher.dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=False,
    )
    assert result.content == "ran:/p"


async def test_an_over_budget_call_is_refused_without_running_the_tool_and_is_audited() -> None:
    # The budget refusal lives in the dispatcher, not the caller (ADR-0009 budget addendum),
    # precisely so it is audited like every other dispatch: a refusal the audit trail never
    # sees would break the one-record-per-dispatch contract where it matters most.
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.is_error is True
    assert result.content == BUDGET_EXHAUSTED_MSG
    assert result.trust is Trust.TRUSTED  # our own message, so it neither fences nor taints
    (record,) = sink.records
    assert (record.name, record.ok, record.detail) == ("send", False, BUDGET_EXHAUSTED_MSG)


async def test_an_over_budget_gated_call_never_reaches_the_confirmer() -> None:
    # Ordering (ADR-0009 budget addendum decision 3): the budget is checked ahead of the gate,
    # so a model emitting hundreds of gated calls cannot turn the spam bound into a flood of
    # confirmation prompts at the user.
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.content == BUDGET_EXHAUSTED_MSG  # not USER_DECLINED_MSG, and it never ran
    assert confirmer.requests == ()  # never consulted


async def test_an_over_budget_gated_call_on_a_tainted_turn_reports_the_budget() -> None:
    # Both blocks apply; the budget is the one reported, because it is checked first. Either
    # message would be safe (neither runs the tool), but the model should read the reason that
    # actually stopped it, so it stops calling tools rather than retrying in a fresh turn.
    result = await _outbound(RecordingAuditSink(), None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.content == BUDGET_EXHAUSTED_MSG


async def test_a_within_budget_call_is_unaffected() -> None:
    # The default keeps every existing path byte-for-byte: no refusal is the old dispatch.
    result = await _outbound(RecordingAuditSink(), None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=None,
    )
    assert result.content == "ran:/p"


def test_the_dispatcher_prices_a_call_from_the_policy_it_was_given() -> None:
    # The loop asks the dispatcher what a call costs (ADR-0009 cost addendum), so the price
    # rides with the gateway that runs the tool rather than being restated per loop.
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        policy=DispatchPolicy(costs=ToolCostPolicy({"send": 4})),
    )
    assert dispatcher.cost_of("send") == 4
    # An unadvertised name is priced too, not free: it still reaches dispatch and still costs
    # a round trip, so a model inventing names cannot dispatch without limit.
    assert dispatcher.cost_of("invented") == DEFAULT_TOOL_COST


def test_a_dispatcher_built_without_a_policy_prices_every_call_at_one() -> None:
    dispatcher = _dispatcher(
        InMemoryToolRegistry({"read": (_spec("read"), _ran)}), RecordingAuditSink()
    )
    assert dispatcher.cost_of("read") == 1


async def test_a_redundant_call_is_refused_without_running_the_tool_and_is_audited() -> None:
    # The second refusal reason rides the same machinery as the first (ADR-0009 salience
    # addendum): the caller decides, the dispatcher states it, and the audit trail sees it. A
    # repeat the loop dropped on its own would be the one runaway shape no record could show.
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=DispatchRefusal.REDUNDANT,
    )
    assert result.is_error is True
    assert result.content == REDUNDANT_MSG
    assert result.trust is Trust.TRUSTED  # our own message, so it neither fences nor taints
    (record,) = sink.records
    assert (record.name, record.ok, record.detail) == ("send", False, REDUNDANT_MSG)


async def test_a_redundant_gated_call_never_reaches_the_confirmer() -> None:
    # What caps confirmation spam: the gate consults the Confirmer per dispatch, so a model
    # re-emitting a declined send would re-ask the user every round with only the budget of
    # thirty two stopping it. Refusing ahead of the gate turns that into at most two cards.
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
        refusal=DispatchRefusal.REDUNDANT,
    )
    assert result.content == REDUNDANT_MSG  # not USER_DECLINED_MSG, and it never ran
    assert confirmer.requests == ()  # never consulted


def test_the_dispatcher_judges_salience_with_the_policy_it_was_given() -> None:
    # The loop asks the dispatcher, as it does for a price, so all three declarations travel
    # with the gateway. The history is the loop's, which is why it is an argument.
    call = ToolCall(id="c2", name="send", arguments={"path": "/p"})
    already = [[ToolCall(id="c1", name="send", arguments={"path": "/p"})]]
    assert _outbound(RecordingAuditSink(), None).admits(call, already) is False
    permissive = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        policy=DispatchPolicy(salience=ALWAYS_SALIENT),
    )
    assert permissive.admits(call, already) is True


def test_the_policy_freezes_the_gated_names_it_was_handed() -> None:
    # A live set on the policy would let whoever built it keep editing the gate afterwards,
    # which is the one declaration that must not move once the process is up.
    names = {"send"}
    policy = DispatchPolicy(gated_names=names)
    names.add("read")
    assert policy.gated_names == frozenset({"send"})


async def test_the_confirm_reason_is_the_policy_per_tool_text_when_declared() -> None:
    # ADR-0030 decision 1: the generic "outbound or irreversible" line would be false on some
    # cards (the escalate card above all), so a policy may declare what one tool's card says.
    confirmer = RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gate_reasons={"send": "this hands your words to a stranger"}),
    )
    await dispatcher.dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    (request,) = confirmer.requests
    assert request.reason == "this hands your words to a stranger"


async def test_a_tool_without_a_declared_reason_keeps_the_generic_gate_text() -> None:
    # The per-tool map is an overlay, not a replacement: unnamed tools keep the generic
    # reason, so declaring one card's text cannot blank another's.
    confirmer = RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gate_reasons={"other_tool": "unrelated"}),
    )
    await dispatcher.dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    (request,) = confirmer.requests
    assert "outbound or irreversible" in request.reason


def test_the_policy_freezes_the_gate_reasons_it_was_handed() -> None:
    # Same argument as the gated names: card text is a consent surface, and whoever built the
    # policy must not be able to rewrite what the user is told after the process is up.
    reasons = {"send": "before"}
    policy = DispatchPolicy(gate_reasons=reasons)
    reasons["send"] = "after"
    assert policy.gate_reasons["send"] == "before"


async def test_the_audit_line_names_the_work_the_call_was_made_for() -> None:
    # The trail's own reading (ADR-0009 named-work addendum): a line says which chat, which
    # turn and which subagent task the call was dispatched for, all three off the stamp the
    # dispatcher put on the call, so the record outlives the process holding any of them.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-1", turn_id="t-1", task_id="st-1"),
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("s-1", "t-1", "st-1")


async def test_an_unattributed_dispatch_records_no_work() -> None:
    # The ticker's own dispatch and any direct caller: the line says nothing rather than
    # borrowing an id, exactly as `TurnStamp.session_id` has always left the chat empty.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"})
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("", "", "")


async def test_a_refused_call_is_named_like_every_other_dispatch() -> None:
    # The refusal returns before the gate and before the registry, so it is the path that
    # would lose the attribution if the stamp were applied any later than it is. A refused
    # call is exactly the one an operator reconstructs a runaway turn from.
    sink = RecordingAuditSink()
    await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-2", turn_id="t-2"),
        refusal=DispatchRefusal.BUDGET,
    )
    (record,) = sink.records
    assert (record.ok, record.session_id, record.turn_id) == (False, "s-2", "t-2")


async def test_a_gate_denial_is_named_too() -> None:
    # And the other early return: a gated call on a tainted turn never reaches the tool, so
    # its line is the only trace that the turn asked for the action at all.
    sink = RecordingAuditSink()
    await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-3", turn_id="t-3", tainted=True),
        gated=True,
    )
    (record,) = sink.records
    assert (record.detail, record.session_id, record.turn_id) == (DENIED_MSG, "s-3", "t-3")


async def test_a_model_cannot_forge_the_work_its_call_is_audited_under() -> None:
    # The stamp on the call is overwritten at dispatch (ADR-0018/0027), so a model that wrote
    # a stamp of its own cannot attribute its call to another turn or launder it into none.
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    forged = TurnStamp(session_id="victim", turn_id="t-elsewhere", task_id="st-elsewhere")
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"}, stamp=forged),
        stamp=TurnStamp(session_id="s-4", turn_id="t-4"),
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("s-4", "t-4", "")
