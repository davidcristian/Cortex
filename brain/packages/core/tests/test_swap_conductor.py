"""The swap sequence, step by step: what a handoff does when nothing goes wrong, and when it does.
"""

import asyncio
import logging
from collections.abc import Mapping, Sequence

import pytest
import swap_harness as harness
from swap_harness import (
    Fakes,
    Gate,
    RecordingHandoffStore,
    ScriptedBrainBackend,
    assert_the_window_announced_real_progress,
    build_harness,
)

from cortex_core import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    BUDGET_EXHAUSTED_MSG,
    CAPTURE_SCREEN_TOOL_NAME,
    DRAIN_TIMEOUT_NOTE,
    DRAINING_DETAIL,
    ESCALATE_TOOL_NAME,
    LOADING_DETAIL,
    POOL_DRAINING_MSG,
    RESTORE_FAILED_NOTE,
    RESTORING_DETAIL,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    WORKING_DETAIL,
    CaptureScreenTool,
    DispatchBudget,
    EscalateToBrainTool,
    EscalationSlot,
    HandoffState,
    HandoffStoreError,
    InMemoryBodyGateway,
    InMemoryToolRegistry,
    ModelHostState,
    RecordingAuditSink,
    RecordingConfirmer,
    ScriptedModelHost,
    StatusUpdate,
    SubagentAdmissionError,
    SystemClock,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnCapabilities,
    TurnEvent,
    UrlRedactingGuardrail,
)
from cortex_core.composite import CompositeToolRegistry
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop


def _texts(events: Sequence[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


def _states(events: Sequence[TurnEvent]) -> list[str]:
    return [event.detail for event in events if isinstance(event, StatusUpdate)]


def _reading_registry() -> InMemoryToolRegistry:
    """One tool the deep model can spend its carried budget on."""

    async def handler(arguments: Mapping[str, object]) -> str:
        del arguments
        return "what the tool read"

    return InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a thing", parameters={}), handler)}
    )


async def test_a_clean_handoff_walks_the_record_through_its_states() -> None:
    """The whole sequence: snapshot READY, swap, BRAIN_ACTIVE, answer, swap back, DONE, delete."""
    live = build_harness()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert live.handoffs.states == [
        HandoffState.READY,
        HandoffState.BRAIN_ACTIVE,
        HandoffState.DONE,
    ]
    assert live.handoffs.deleted == [harness.TURN]
    assert await live.handoffs.active() is None
    # BRAIN_ACTIVE is written only after the health gate passed, never on a start call alone.
    assert live.host.calls == [
        ("stop", "cortex"),
        ("start", "brain"),
        ("status", "brain"),
        ("stop", "brain"),
        ("start", "cortex"),
        ("status", "cortex"),
    ]
    assert live.host.running == {"cortex"}
    assert _texts(events) == "a deep answer"
    assert {event.state for event in events if isinstance(event, StatusUpdate)} == {SWAPPING_STATE}
    # The user is told what the machine is doing through the whole window, in order, and the
    # strings themselves are the assertion: a count cannot tell a reordered or mislabelled
    # window from a truthful one, and these four are the only thing the user sees for minutes.
    assert _states(events) == [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    # And each of them was true when it crossed. An order among the four strings is satisfied
    # by four strings emitted at any four moments, so the work each one announces is what
    # actually pins it (the harness holds that contract, and the chaos suite runs it too).
    assert_the_window_announced_real_progress(live)


async def test_the_deep_model_answers_from_the_store_and_persists_a_second_message() -> None:
    """The one hard rule, end to end: the deep phase's context comes back out of the stores."""
    live = build_harness()
    await live.seed_session()
    await harness.run_handoff(live, harness.armed_slot())
    assert live.backend.models == ["brain"]
    # It read the conversation back rather than being handed it: the user message and the
    # cortex's wrap-up are both in what the deep model saw.
    seen = [message.text for message in live.backend.seen]
    assert harness.USER_TEXT in seen
    assert harness.CORTEX_TEXT in seen
    history = [
        (message.role.value, message.text)
        for message in await live.sessions.history(harness.SESSION)
    ]
    assert history == [
        ("user", harness.USER_TEXT),
        ("assistant", harness.CORTEX_TEXT),
        ("assistant", "a deep answer"),  # a SECOND assistant message under the same turn id
    ]


async def test_the_deep_phase_resumes_the_carried_budget_and_taint() -> None:
    """A swap must not refill the turn's allowance, nor forget what it read."""
    spent = DispatchBudget(limit=4)
    assert spent.charge(3) is True  # one dispatch left when the cortex escalated
    ledger = TaintLedger()
    ledger.ingest_untrusted("see http://evil.test/x", source=None)
    audit = RecordingAuditSink()
    live = build_harness(
        Fakes(
            backend=ScriptedBrainBackend(
                chunks=("go to http://evil.test/x",),
                tool_calls=(
                    ToolCall(id="c1", name="read", arguments={}),
                    ToolCall(id="c2", name="read", arguments={}),
                ),
            )
        ),
        capabilities=TurnCapabilities(
            tools=ToolDispatcher(_reading_registry(), audit, SystemClock()),
            guardrail=UrlRedactingGuardrail(),
        ),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot(taint=ledger, budget=spent))
    # The carried position bound the deep phase: the first call fits the one remaining
    # allowance and the second is refused, which a refilled pool would have granted.
    assert [invocation.ok for invocation in audit.records] == [True, False]
    assert audit.records[-1].detail == BUDGET_EXHAUSTED_MSG
    # And the ledger arrived tainted with its evidence, so the guardrail still scrubs the URL
    # the cortex laundered into the turn before the swap.
    assert "http://evil.test/x" not in _texts(events)
    assert await live.handoffs.get(harness.TURN) is None  # a clean handoff deletes the record


async def test_a_second_concurrent_handoff_is_refused_without_evicting_anything(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One GPU means one handoff: the second is told so and nothing is unloaded."""
    live = build_harness()
    await live.seed_session()
    await live.handoffs.put(
        harness.armed_slot().snapshot(
            turn_id="t-other", session_id=harness.SESSION, requested_at=SystemClock().now()
        )
    )
    with caplog.at_level(logging.WARNING, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == ALREADY_ACTIVE_NOTE
    assert live.host.calls == []  # nothing was stopped, so the cortex never stopped serving
    assert live.backend.calls == 0
    assert [record.message for record in caplog.records] == [
        "refusing a handoff while the store still has one in flight"
    ]


async def test_a_swap_that_finds_the_gpu_already_handed_over_says_so_and_not_that_it_broke() -> (
    None
):
    """The scope's backstop refusal is not a swap failure, and the user must not be told it is."""
    live = build_harness()
    await live.seed_session()
    async with live.manager.swap_scope(live.residency.brain_model):
        assert live.host.running == {"brain"}  # the GPU really is somebody else's
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == ALREADY_ACTIVE_NOTE
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert live.backend.calls == 0  # it never reached the deep model
    assert live.host.calls.count(("start", "brain")) == 1  # and never swapped a second time
    assert live.host.running == {"cortex"}  # the scope it lost to put the cortex back


async def test_a_handoff_store_that_cannot_record_the_snapshot_changes_nothing() -> None:
    """A failure before anything is evicted costs the handoff and nothing else."""
    live = build_harness(
        Fakes(handoffs=RecordingHandoffStore(fail=HandoffStoreError("redis is gone")))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == STORE_FAILED_NOTE
    assert live.host.calls == []
    assert live.backend.calls == 0


async def test_a_handoff_store_that_cannot_be_read_refuses_the_handoff_the_same_way() -> None:
    """The precondition read fails closed too: no record, no eviction, an honest note."""

    class _Unreadable(RecordingHandoffStore):
        async def active(self) -> None:
            msg = "redis is gone"
            raise HandoffStoreError(msg)

    live = build_harness(Fakes(handoffs=_Unreadable()))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == STORE_FAILED_NOTE
    assert live.host.calls == []
    assert live.handoffs.states == []  # nothing was even written


async def test_a_drain_that_times_out_aborts_before_anything_is_evicted() -> None:
    """The straggler rule: v1 kills nothing, so the swap does not happen at all."""
    live = build_harness(residency=harness.plan(drain_timeout_s=0.0))
    await live.seed_session()
    held = asyncio.Event()
    release = asyncio.Event()

    async def in_flight() -> None:
        async with live.scheduler.admit(harness.request()):
            held.set()
            await release.wait()

    task = asyncio.create_task(in_flight())
    async with asyncio.timeout(5.0):
        await held.wait()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == DRAIN_TIMEOUT_NOTE
    assert live.host.calls == []  # nothing evicted: the cortex is still serving
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert not task.done()
    release.set()
    await task
    # The window was released even though the handoff aborted, so delegation resumes.
    async with live.scheduler.admit(harness.request()):
        pass


async def test_a_deployment_without_a_subagent_pool_has_nothing_to_drain() -> None:
    """No pool, no drain step: the handoff runs with the scheduler simply absent."""
    live = build_harness(with_scheduler=False)
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.handoffs.states[-1] is HandoffState.DONE
    assert _states(events) == [DRAINING_DETAIL, LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    assert_the_window_announced_real_progress(live)


async def test_a_deep_model_that_will_not_load_ends_the_turn_honestly() -> None:
    """The swap-in failure direction: the cortex is back and the user is told plainly."""
    live = build_harness(
        Fakes(host=ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM"}))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert live.host.running == {"cortex"}
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert live.backend.calls == 0  # the deep model never ran, so nothing half-ran


async def test_a_deep_model_that_never_becomes_ready_ends_the_turn_honestly() -> None:
    live = build_harness(
        Fakes(
            host=ScriptedModelHost(
                running=["cortex"], status_override={"brain": ModelHostState.LOADING}
            )
        ),
        residency=harness.plan(load_timeout_s=0.0),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == SWAP_FAILED_NOTE
    assert live.host.running == {"cortex"}


async def test_a_deep_model_that_dies_mid_answer_keeps_its_partial_text_with_a_note() -> None:
    """The parts-so-far discipline: what it produced is persisted, and the note says why."""
    live = build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("half an ", "never streamed"), fail_after=1))
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "half an " + BRAIN_FAILED_NOTE
    persisted = [message.text for message in await live.sessions.history(harness.SESSION)]
    assert persisted[-1] == "half an " + BRAIN_FAILED_NOTE
    assert live.handoffs.states == [
        HandoffState.READY,
        HandoffState.BRAIN_ACTIVE,
        HandoffState.FAILED,
    ]
    assert live.host.running == {"cortex"}  # and the cortex is serving again


async def test_a_cortex_that_cannot_be_restored_says_so_on_the_stream() -> None:
    """The gravest failure: the deep answer stands, and the note warns about the next turn."""
    live = build_harness(
        Fakes(
            host=ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
        )
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer" + RESTORE_FAILED_NOTE
    assert live.handoffs.states[-1] is HandoffState.FAILED
    assert live.host.calls.count(("start", "cortex")) == 2  # it tried, then retried


class _FailsLate(RecordingHandoffStore):
    """A store that goes away after the snapshot: every state written from then on is refused."""

    async def transition(self, handoff_id: str, state: HandoffState) -> bool:
        del handoff_id, state
        msg = "redis went away mid-handoff"
        raise HandoffStoreError(msg)


async def test_a_store_that_fails_while_settling_the_record_does_not_fail_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A store that dies late costs the record, never the turn, and never the NEXT handoff."""
    live = build_harness(Fakes(handoffs=_FailsLate()))
    await live.seed_session()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.host.running == {"cortex"}
    assert [record.message for record in caplog.records] == [
        "could not record the handoff's state",
        "could not record the handoff's state",
    ]
    assert live.handoffs.deleted == [harness.TURN]  # the claim is released by dropping it
    assert await live.handoffs.active() is None  # so nothing reads a finished handoff as live


async def test_a_store_that_cannot_even_drop_the_record_says_what_is_now_stuck(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The end of the line: the release fails too, so the log has to name what that costs."""

    class _AlsoRefusesTheDelete(_FailsLate):
        async def delete(self, handoff_id: str) -> None:
            del handoff_id
            msg = "redis is still gone"
            raise HandoffStoreError(msg)

    live = build_harness(Fakes(handoffs=_AlsoRefusesTheDelete()))
    await live.seed_session()
    with caplog.at_level(logging.ERROR, logger="cortex_core.swap_conductor"):
        events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert live.host.running == {"cortex"}
    assert [record.message for record in caplog.records][-1] == (
        "could not release the finished handoff; escalation stays refused until a restart"
    )


async def test_a_turn_that_looked_at_the_screen_after_escalating_ends_with_a_note() -> None:
    """The ordering the escalation tool cannot see, driven through the real loop end to end."""
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([EscalateToBrainTool(), CaptureScreenTool(InMemoryBodyGateway())]),
        audit,
        SystemClock(),
        confirmer=RecordingConfirmer(answer=True),  # the user approved the handoff
    )
    slot = harness.armed_slot(brief=None)
    assert slot.refs is not None
    working = slot.refs.working
    cortex = ScriptedBrainBackend(
        chunks=("handing this over",),
        tool_calls=(
            ToolCall(id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": harness.BRIEF}),
            ToolCall(id="c2", name=CAPTURE_SCREEN_TOOL_NAME, arguments={}),
        ),
    )
    context = ToolLoopContext(
        dispatcher=dispatcher,
        clock=SystemClock(),
        turn_id=harness.TURN,
        taint=slot.refs.taint,
        nonce=slot.refs.nonce,
        session_id=harness.SESSION,
        escalation=slot,
    )
    async for _delta in stream_tool_loop(cortex, "cortex", working, context):
        pass

    assert slot.brief == harness.BRIEF, "the escalation really was queued before the capture"
    assert [line.name for line in audit.records] == [ESCALATE_TOOL_NAME, CAPTURE_SCREEN_TOOL_NAME]
    assert [len(message.images) for message in working[slot.refs.base_len :]].count(1) == 1

    live = build_harness()
    await live.seed_session()
    events = await harness.run_handoff(live, slot)

    assert _texts(events) == (
        "\n\n(This turn looked at your screen, and a picture cannot be handed to the deep model, "
        "so the handoff was not started. Nothing was unloaded. Ask again in a new message if you "
        "still want the deep model.)"
    )
    assert _states(events) == [], "nothing was announced, because nothing was done"
    # And no record was written at all, which is what makes the record's own ``opaque`` field
    # defence in depth rather than a live path: the refusal is upstream of the store.
    assert live.handoffs.states == []
    assert live.host.calls == []  # the cortex never stopped serving
    assert live.backend.calls == 0  # the deep model was never asked anything
    assert live.handoffs.states == []  # and no record was written to be settled


async def test_the_deep_phase_cannot_escalate_to_itself() -> None:
    """No slot rides the deep phase's dispatches, so a second handoff cannot be queued."""
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        CompositeToolRegistry([EscalateToBrainTool()], remote=InMemoryToolRegistry({})),
        audit,
        SystemClock(),
        # An approving confirmer, as a live stream's dispatcher has: the gate is not what stops
        # the deep model here, the missing slot is.
        confirmer=RecordingConfirmer(answer=True),
    )
    stowaway = EscalationSlot()
    live = build_harness(
        Fakes(
            backend=ScriptedBrainBackend(
                chunks=("thinking",),
                tool_calls=(
                    ToolCall(
                        id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deeper still"}
                    ),
                ),
            )
        ),
        capabilities=TurnCapabilities(tools=dispatcher, escalation=stowaway),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    (invocation,) = audit.records
    assert invocation.ok is False
    assert "escalation is not available for this turn" in invocation.detail
    assert stowaway.brief is None  # nothing was queued behind the running handoff
    assert _texts(events) == "thinking"


def _coresident_harness(gate: Gate, *, coresident: bool) -> harness.Harness:
    """The one deployment shape this pair of tests differs on, everything else identical."""
    return build_harness(
        Fakes(
            host=ScriptedModelHost(running=["cortex", "subagent-gpu"]),
            backend=ScriptedBrainBackend(gate=gate, gate_after=1),
        ),
        residency=harness.plan(evict_models=("subagent-gpu",), coresident=coresident),
    )


async def _paused_mid_phase(live: harness.Harness, gate: Gate) -> asyncio.Task[list[TurnEvent]]:
    """Drive a handoff until the deep model's stream is mid-flight, and hold it there."""
    task = asyncio.create_task(harness.run_handoff(live, harness.armed_slot()))
    await gate.arrived()
    return task


async def test_a_coresident_handoff_keeps_its_peers_and_keeps_delegating() -> None:
    """The opt-in reversal of brain-runs-alone, asserted where it is observable: mid-phase."""
    gate = Gate()
    live = _coresident_harness(gate, coresident=True)
    await live.seed_session()
    task = await _paused_mid_phase(live, gate)
    # Mid-phase: the deep model holds the card and the peer tier never left it.
    assert live.host.running == {"brain", "subagent-gpu"}
    async with live.scheduler.admit(harness.request()):
        pass  # a quiesced pool raises SubagentAdmissionError here instead
    gate.release.set()
    events = await task
    assert live.scheduler.drains == 0  # the window was never entered, not merely left early
    assert ("stop", "subagent-gpu") not in live.host.calls
    assert live.handoffs.states[-1] is HandoffState.DONE
    assert _texts(events) == "a deep answer"


async def test_the_shipped_default_still_evicts_its_peers_and_refuses_a_spawn() -> None:
    """The same shape with the opt-in off, which is what makes the case above non-vacuous.

    Read at the identical instant: the tier is stopped rather than serving, and the admission
    the co-resident deployment takes is refused with the drain window's own message.
    """
    gate = Gate()
    live = _coresident_harness(gate, coresident=False)
    await live.seed_session()
    task = await _paused_mid_phase(live, gate)
    assert live.host.running == {"brain"}  # the peer was evicted for the deep model
    with pytest.raises(SubagentAdmissionError, match=POOL_DRAINING_MSG):
        async with live.scheduler.admit(harness.request()):
            pass  # pragma: no cover - admit raises before the block is ever entered
    gate.release.set()
    await task
    assert live.scheduler.drains == 1
    assert ("stop", "subagent-gpu") in live.host.calls
    assert live.host.running == {"cortex", "subagent-gpu"}  # and it is restarted at the end


async def test_a_coresident_handoff_does_not_announce_a_drain_it_never_performs() -> None:
    """The window's first status is dropped rather than lied about (the other three stand)."""
    live = build_harness(residency=harness.plan(coresident=True))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(events) == "a deep answer"
    assert _states(events) == [LOADING_DETAIL, WORKING_DETAIL, RESTORING_DETAIL]
    assert live.scheduler.drains == 0
