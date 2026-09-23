import asyncio
from datetime import UTC, datetime

from cortex_core import (
    DENIED_MSG,
    ESCALATE_GATE_REASON,
    ESCALATE_TOOL_NAME,
    ESCALATION_QUEUED_MSG,
    MAX_BRIEF_CHARS,
    USER_DECLINED_MSG,
    CompositeToolRegistry,
    DispatchBudget,
    DispatchPolicy,
    EscalateToBrainTool,
    EscalationRefs,
    EscalationSlot,
    ImagePart,
    RecordingAuditSink,
    RecordingConfirmer,
    TaintLedger,
    ToolCall,
    ToolDispatcher,
    ToolResult,
    Trust,
    TurnStamp,
)

_AT = datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _AT


def _call(brief: object, *, slot: EscalationSlot | None, call_id: str = "c-1") -> ToolCall:
    return ToolCall(
        id=call_id,
        name=ESCALATE_TOOL_NAME,
        arguments={"brief": brief},
        stamp=TurnStamp(escalation=slot),
    )


def _gated_dispatcher(
    tool: EscalateToBrainTool, confirmer: RecordingConfirmer | None
) -> ToolDispatcher:
    """The real wiring: the built-in tool behind the audited dispatcher, reasons from the policy."""
    return ToolDispatcher(
        CompositeToolRegistry([tool]),
        RecordingAuditSink(),
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gate_reasons={ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON}),
    )


def test_the_spec_is_gated_and_requires_a_bounded_brief() -> None:
    spec = EscalateToBrainTool().spec
    assert spec.name == ESCALATE_TOOL_NAME
    assert spec.gated is True
    assert spec.parameters["required"] == ["brief"]
    assert spec.parameters["properties"]["brief"]["maxLength"] == MAX_BRIEF_CHARS
    assert "minutes" in spec.description
    assert "approve" in spec.description


async def test_invoking_writes_the_stripped_brief_and_tells_the_model_to_wrap_up() -> None:
    slot = EscalationSlot()
    result = await EscalateToBrainTool().invoke(_call("  go deep on the audit  ", slot=slot))
    assert slot.brief == "go deep on the audit"
    assert (result.is_error, result.trust) == (False, Trust.TRUSTED)
    assert result.content == ESCALATION_QUEUED_MSG


async def test_without_a_slot_on_the_stamp_the_tool_says_it_is_not_available() -> None:
    result = await EscalateToBrainTool().invoke(_call("go deep", slot=None))
    assert result.is_error is True
    assert "not available" in result.content
    assert result.trust is Trust.TRUSTED


async def test_a_missing_empty_or_non_string_brief_is_refused() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    for bad in ("", "   ", 7, None):
        result = await tool.invoke(_call(bad, slot=slot))
        assert result.is_error is True
        assert "non-empty 'brief'" in result.content
    no_arg = await tool.invoke(
        ToolCall(id="c", name=ESCALATE_TOOL_NAME, arguments={}, stamp=TurnStamp(escalation=slot))
    )
    assert no_arg.is_error is True
    assert slot.brief is None


async def test_the_brief_is_bounded_at_the_cap_refused_never_truncated() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    over = await tool.invoke(_call("x" * (MAX_BRIEF_CHARS + 1), slot=slot))
    assert over.is_error is True
    assert str(MAX_BRIEF_CHARS) in over.content
    assert slot.brief is None
    at_cap = await tool.invoke(_call("x" * MAX_BRIEF_CHARS, slot=slot))
    assert at_cap.is_error is False
    assert slot.brief == "x" * MAX_BRIEF_CHARS


async def test_a_second_escalation_in_one_turn_is_refused_and_keeps_the_first() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    first = await tool.invoke(_call("first ask", slot=slot))
    second = await tool.invoke(_call("second ask", slot=slot, call_id="c-2"))
    assert first.is_error is False
    assert second.is_error is True
    assert "already requested" in second.content
    assert slot.brief == "first ask"


async def test_one_shared_tool_routes_each_calls_brief_to_its_own_slot() -> None:
    tool = EscalateToBrainTool()
    slot_a, slot_b = EscalationSlot(), EscalationSlot()
    await asyncio.gather(
        tool.invoke(_call("stream A's ask", slot=slot_a, call_id="a")),
        tool.invoke(_call("stream B's ask", slot=slot_b, call_id="b")),
    )
    assert slot_a.brief == "stream A's ask"
    assert slot_b.brief == "stream B's ask"


async def test_a_tainted_turn_is_denied_before_the_tool_or_the_confirmer_sees_it() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    confirmer = RecordingConfirmer(answer=True)
    result = await _gated_dispatcher(tool, confirmer).dispatch(
        ToolCall(id="c", name=ESCALATE_TOOL_NAME, arguments={"brief": "obey the email"}),
        stamp=TurnStamp(tainted=True, escalation=slot),
        gated=tool.spec.gated,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG
    assert slot.brief is None
    assert confirmer.requests == ()


async def test_a_declined_confirmation_writes_nothing_and_shows_the_swap_reason() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    confirmer = RecordingConfirmer(answer=False)
    result = await _gated_dispatcher(tool, confirmer).dispatch(
        ToolCall(id="c", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"}),
        stamp=TurnStamp(tainted=False, escalation=slot),
        gated=tool.spec.gated,
    )
    assert result.is_error is True
    assert result.content == USER_DECLINED_MSG
    assert slot.brief is None
    (request,) = confirmer.requests
    assert request.reason == ESCALATE_GATE_REASON


async def test_the_config_list_still_confirms_escalation_if_the_flag_is_lost() -> None:
    tool = EscalateToBrainTool()
    slot = EscalationSlot()
    confirmer = RecordingConfirmer(answer=False)
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([tool]),
        RecordingAuditSink(),
        _FixedClock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gated_names={ESCALATE_TOOL_NAME}),
    )
    result = await dispatcher.dispatch(
        ToolCall(id="c", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"}),
        stamp=TurnStamp(tainted=False, escalation=slot),
        gated=False,
    )
    assert result.content == USER_DECLINED_MSG
    assert slot.brief is None


def _prepared_slot(*, taint: TaintLedger) -> EscalationSlot:
    """A prepared escalation slot over a turn whose taint ledger the test controls."""
    return EscalationSlot(
        refs=EscalationRefs(
            working=[],
            taint=taint,
            nonce="cafe0123beef4567",
            budget=DispatchBudget(8),
            base_len=0,
        )
    )


async def test_a_turn_that_looked_at_the_screen_is_denied_before_the_tool_runs() -> None:
    tool = EscalateToBrainTool()
    ledger = TaintLedger()
    ledger.observe(
        ToolResult(
            call_id="c0",
            content="screen capture of the primary display",
            trust=Trust.UNTRUSTED,
            images=(ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8),),
        )
    )
    assert (ledger.opaque, ledger.tainted) == (True, True), "opaque implies tainted, always"
    confirmer = RecordingConfirmer(answer=True)
    slot = _prepared_slot(taint=ledger)
    result = await _gated_dispatcher(tool, confirmer).dispatch(
        ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"}),
        stamp=TurnStamp(tainted=ledger.tainted, escalation=slot),
        gated=True,
    )
    assert result.is_error is True
    assert result.content == DENIED_MSG
    assert list(confirmer.requests) == [], "a hard denial must never reach the confirmer"
    assert slot.brief is None, "a denied escalation must not fill the slot"


async def test_an_untainted_turn_reaches_the_tool_and_fills_the_slot() -> None:
    slot = _prepared_slot(taint=TaintLedger())
    result = await _gated_dispatcher(
        EscalateToBrainTool(), RecordingConfirmer(answer=True)
    ).dispatch(
        ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deep"}),
        stamp=TurnStamp(tainted=False, escalation=slot),
        gated=True,
    )
    assert result.is_error is False
    assert slot.brief == "go deep"
