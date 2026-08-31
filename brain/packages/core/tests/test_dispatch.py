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
    """A clock fixed at one instant, so audit timestamps can be compared exactly."""

    def now(self) -> datetime:
        return _AT


def _spec(name: str) -> ToolSpec:
    return ToolSpec(name=name, description=name, parameters={"type": "object"})


async def _ran(arguments: Mapping[str, object]) -> str:
    return f"ran:{arguments['path']}"


def _outbound(sink: RecordingAuditSink, confirmer: RecordingConfirmer | None) -> ToolDispatcher:
    """A dispatcher over a recording 'send' tool that reports whether it ran."""
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
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"})
    )
    (record,) = sink.records
    assert record.trust is Trust.UNTRUSTED


async def test_gated_tool_on_a_tainted_turn_is_blocked_without_a_confirmer() -> None:
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG
    assert result.trust is Trust.TRUSTED
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, DENIED_MSG)


async def test_gated_tool_on_a_tainted_turn_is_blocked_even_when_a_confirmer_would_approve() -> (
    None
):
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
    )
    assert result.content == DENIED_MSG
    assert confirmer.requests == ()


async def test_gated_tool_on_a_clean_turn_runs_when_the_user_approves() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
    )
    assert result.content == "ran:/p"
    (request,) = confirmer.requests
    assert request.tool_name == "send"
    assert request.arguments == {"path": "/p"}
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
    assert result.content == USER_DECLINED_MSG
    assert result.trust is Trust.TRUSTED
    assert confirmer.requests != ()
    (record,) = sink.records
    assert (record.ok, record.detail) == (False, USER_DECLINED_MSG)


async def test_gated_tool_on_a_clean_turn_is_declined_without_a_confirmer() -> None:
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
    """A registry that records the exact ToolCall values it was invoked with."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    async def describe_tools(self) -> list[ToolSpec]:
        return []

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        return ToolResult(call_id=call.id, content="ok", trust=Trust.TRUSTED)


async def test_dispatch_stamps_the_turns_provenance_onto_the_invoked_call() -> None:
    registry = _CallRecordingRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="c", name="spawn", arguments={}),
        stamp=TurnStamp(session_id="s-1", tainted=True),
    )
    (stamped,) = registry.calls
    assert stamped.stamp == TurnStamp(session_id="s-1", tainted=True)
    assert (stamped.id, stamped.name) == ("c", "spawn")


async def test_dispatch_overwrites_a_forged_stamp_with_the_turns() -> None:
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
    registry = _CallRecordingRegistry()
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _FixedClock())
    await dispatcher.dispatch(
        ToolCall(id="c", name="spawn", arguments={}, stamp=TurnStamp(tainted=True))
    )
    (stamped,) = registry.calls
    assert stamped.stamp == TurnStamp(session_id="", tainted=False)


async def test_gated_names_gate_a_call_the_snapshot_advertised_as_ungated() -> None:
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
    assert result.content == USER_DECLINED_MSG
    assert confirmer.requests != ()


async def test_gated_names_deny_a_tainted_call_the_snapshot_advertised_as_ungated() -> None:
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
    assert confirmer.requests == ()


async def test_a_name_outside_the_gated_set_stays_ungated() -> None:
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
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.is_error is True
    assert result.content == BUDGET_EXHAUSTED_MSG
    assert result.trust is Trust.TRUSTED
    (record,) = sink.records
    assert (record.name, record.ok, record.detail) == ("send", False, BUDGET_EXHAUSTED_MSG)


async def test_an_over_budget_gated_call_never_reaches_the_confirmer() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.content == BUDGET_EXHAUSTED_MSG
    assert confirmer.requests == ()


async def test_an_over_budget_gated_call_on_a_tainted_turn_reports_the_budget() -> None:
    result = await _outbound(RecordingAuditSink(), None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=True),
        gated=True,
        refusal=DispatchRefusal.BUDGET,
    )
    assert result.content == BUDGET_EXHAUSTED_MSG


async def test_a_within_budget_call_is_unaffected() -> None:
    result = await _outbound(RecordingAuditSink(), None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=None,
    )
    assert result.content == "ran:/p"


def test_the_dispatcher_prices_a_call_from_the_policy_it_was_given() -> None:
    dispatcher = ToolDispatcher(
        InMemoryToolRegistry({"send": (_spec("send"), _ran)}),
        RecordingAuditSink(),
        _FixedClock(),
        policy=DispatchPolicy(costs=ToolCostPolicy({"send": 4})),
    )
    assert dispatcher.cost_of("send") == 4
    assert dispatcher.cost_of("invented") == DEFAULT_TOOL_COST


def test_a_dispatcher_built_without_a_policy_prices_every_call_at_one() -> None:
    dispatcher = _dispatcher(
        InMemoryToolRegistry({"read": (_spec("read"), _ran)}), RecordingAuditSink()
    )
    assert dispatcher.cost_of("read") == 1


async def test_a_redundant_call_is_refused_without_running_the_tool_and_is_audited() -> None:
    sink = RecordingAuditSink()
    result = await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        refusal=DispatchRefusal.REDUNDANT,
    )
    assert result.is_error is True
    assert result.content == REDUNDANT_MSG
    assert result.trust is Trust.TRUSTED
    (record,) = sink.records
    assert (record.name, record.ok, record.detail) == ("send", False, REDUNDANT_MSG)


async def test_a_redundant_gated_call_never_reaches_the_confirmer() -> None:
    confirmer = RecordingConfirmer(answer=True)
    result = await _outbound(RecordingAuditSink(), confirmer).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(tainted=False),
        gated=True,
        refusal=DispatchRefusal.REDUNDANT,
    )
    assert result.content == REDUNDANT_MSG
    assert confirmer.requests == ()


def test_the_dispatcher_judges_salience_with_the_policy_it_was_given() -> None:
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
    names = {"send"}
    policy = DispatchPolicy(gated_names=names)
    names.add("read")
    assert policy.gated_names == frozenset({"send"})


async def test_the_confirm_reason_is_the_policy_per_tool_text_when_declared() -> None:
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
    reasons = {"send": "before"}
    policy = DispatchPolicy(gate_reasons=reasons)
    reasons["send"] = "after"
    assert policy.gate_reasons["send"] == "before"


async def test_the_audit_line_names_the_work_the_call_was_made_for() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-1", turn_id="t-1", task_id="st-1"),
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("s-1", "t-1", "st-1")


async def test_an_unattributed_dispatch_records_no_work() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"})
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("", "", "")


async def test_a_refused_call_is_named_like_every_other_dispatch() -> None:
    sink = RecordingAuditSink()
    await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-2", turn_id="t-2"),
        refusal=DispatchRefusal.BUDGET,
    )
    (record,) = sink.records
    assert (record.ok, record.session_id, record.turn_id) == (False, "s-2", "t-2")


async def test_a_gate_denial_is_named_too() -> None:
    sink = RecordingAuditSink()
    await _outbound(sink, None).dispatch(
        ToolCall(id="c", name="send", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-3", turn_id="t-3", tainted=True),
        gated=True,
    )
    (record,) = sink.records
    assert (record.detail, record.session_id, record.turn_id) == (DENIED_MSG, "s-3", "t-3")


async def test_a_model_cannot_forge_the_work_its_call_is_audited_under() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    forged = TurnStamp(session_id="victim", turn_id="t-elsewhere", task_id="st-elsewhere")
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="c", name="read", arguments={"path": "/p"}, stamp=forged),
        stamp=TurnStamp(session_id="s-4", turn_id="t-4"),
    )
    (record,) = sink.records
    assert (record.session_id, record.turn_id, record.task_id) == ("s-4", "t-4", "")


async def test_the_audit_line_names_the_call_that_was_dispatched() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="call-7", name="read", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="s-1", turn_id="t-1"),
    )
    (record,) = sink.records
    assert record.call_id == "call-7"


async def test_a_refused_and_a_denied_call_name_themselves_too() -> None:
    sink = RecordingAuditSink()
    await _outbound(sink, None).dispatch(
        ToolCall(id="call-8", name="send", arguments={}), refusal=DispatchRefusal.BUDGET
    )
    await _outbound(sink, None).dispatch(
        ToolCall(id="call-9", name="send", arguments={}),
        stamp=TurnStamp(tainted=True),
        gated=True,
    )
    refused, denied = sink.records
    assert (refused.call_id, denied.call_id) == ("call-8", "call-9")
    assert (refused.detail, denied.detail) == (DispatchRefusal.BUDGET.message, DENIED_MSG)


async def test_a_fired_items_identity_reaches_the_line_off_the_stamp() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="schedule-t1", name="read", arguments={"path": "/p"}),
        stamp=TurnStamp(session_id="chat-1", item_id="t1"),
    )
    (record,) = sink.records
    assert (record.item_id, record.call_id) == ("t1", "schedule-t1")


async def test_a_model_cannot_counterfeit_a_fire_by_spelling_the_ticker_prefix() -> None:
    sink = RecordingAuditSink()
    registry = InMemoryToolRegistry({"read": (_spec("read"), _ran)})
    forged = TurnStamp(session_id="victim", item_id="t-victim")
    await _dispatcher(registry, sink).dispatch(
        ToolCall(id="schedule-t-victim", name="read", arguments={"path": "/p"}, stamp=forged),
        stamp=TurnStamp(session_id="s-5", turn_id="t-5"),
    )
    (record,) = sink.records
    assert record.call_id == "schedule-t-victim"
    assert record.item_id == ""
    assert (record.session_id, record.turn_id) == ("s-5", "t-5")
