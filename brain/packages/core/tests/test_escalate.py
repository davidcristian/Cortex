"""Behavior tests for the ``escalate_to_brain`` built-in (ADR-0030 decision 1).

The safety-critical half is the gate composition: a tainted turn's escalation is hard-denied
by the dispatcher with the confirmer never consulted, a declined confirmation never writes the
slot, and the model-authored brief is bounded before it can enter the handoff record. The tool
itself holds no per-stream state: the slot rides each dispatch's stamp, so one shared instance
serves every stream (the ``spawn_subagents`` progress-sink discipline).

Distrust-green proofs (AGENTS.md), each verified by mutation when this landed:
- weakening the dispatcher's tainted-turn check reddens the tainted test here;
- skipping the declined-confirmation branch reddens the declined test (the slot gets written);
- deleting the tool's length check reddens the over-bound test;
- caching the slot on the tool instance reddens the two-slot isolation test.
"""

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
    DispatchPolicy,
    EscalateToBrainTool,
    EscalationSlot,
    RecordingAuditSink,
    RecordingConfirmer,
    ToolCall,
    ToolDispatcher,
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
    """The wiring shape: the built-in behind the audited dispatcher, reasons from the policy."""
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
    assert spec.gated is True  # the tool's own flag; the config backstop is belt-and-braces
    assert spec.parameters["required"] == ["brief"]
    assert spec.parameters["properties"]["brief"]["maxLength"] == MAX_BRIEF_CHARS
    # Honest advertisement (the spawn-spec discipline): the swap's cost and the user's say
    # are stated plainly, not sold as a free upgrade.
    assert "minutes" in spec.description
    assert "approve" in spec.description


async def test_invoking_writes_the_stripped_brief_and_tells_the_model_to_wrap_up() -> None:
    slot = EscalationSlot()
    result = await EscalateToBrainTool().invoke(_call("  go deep on the audit  ", slot=slot))
    assert slot.brief == "go deep on the audit"
    assert (result.is_error, result.trust) == (False, Trust.TRUSTED)
    assert result.content == ESCALATION_QUEUED_MSG


async def test_without_a_slot_on_the_stamp_the_tool_refuses_honestly() -> None:
    # An escalation-less wiring, or a turn-less caller (the ticker): nothing could consume a
    # brief, so the tool says so instead of pretending a handoff is coming.
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
    assert slot.brief is None  # nothing invalid ever landed in the slot


async def test_the_brief_is_bounded_at_the_cap_refused_never_truncated() -> None:
    # The brief is the one model-authored string this tool persists toward the handoff
    # record; an oversized one is refused whole (the spawn batch-cap precedent), because a
    # silently truncated handover would prime the deep model with an ask that looks complete.
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
    # Isolation is per call, never per instance: the slot rides each call's stamp, so the one
    # shared tool serves two concurrent streams without a field to leak a brief across turns
    # (the spawn progress-sink proof shape). A slot cached on the instance would cross them.
    tool = EscalateToBrainTool()
    slot_a, slot_b = EscalationSlot(), EscalationSlot()
    await asyncio.gather(
        tool.invoke(_call("stream A's ask", slot=slot_a, call_id="a")),
        tool.invoke(_call("stream B's ask", slot=slot_b, call_id="b")),
    )
    assert slot_a.brief == "stream A's ask"
    assert slot_b.brief == "stream B's ask"


async def test_a_tainted_turn_is_denied_before_the_tool_or_the_confirmer_sees_it() -> None:
    # The safety spine (ADR-0030 decision 1): injected content must never force an eviction,
    # so a tainted turn's escalation is blocked outright by the existing dispatcher gate. An
    # approving confirmer changes nothing, because it is never consulted.
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
    assert slot.brief is None  # the tool was never invoked
    assert confirmer.requests == ()  # and the user was never even asked


async def test_a_declined_confirmation_writes_nothing_and_shows_the_swap_reason() -> None:
    # The user's "no" must leave no trace a later loop boundary could act on: the slot stays
    # empty, so there is nothing to snapshot and no READY record can exist. The card carried
    # the app-authored swap reason, not the generic outbound/irreversible text.
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


async def test_the_config_backstop_gates_escalation_even_if_the_flag_is_lost() -> None:
    # Defense in depth (ADR-0022's authoritative-backstop argument): even if a dispatch
    # arrived without the advertised gated flag, the policy's gated names still gate it.
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
        gated=False,  # the lost-flag shape
    )
    assert result.content == USER_DECLINED_MSG
    assert slot.brief is None
