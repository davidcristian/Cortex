"""The swap sequence, step by step: what a handoff does when nothing goes wrong, and when it does.

The kill-at-every-boundary half lives in ``test_swap_chaos.py``; this suite pins the sequence
itself: the ordering the ADR fixes, the record's states, what reaches the user's stream, and the
five refusals that end a handoff before or instead of a swap. Composition is real throughout
(the conductor drives the real residency manager, the real drain, and the real deep phase over
the scripted host), so an ordering mistake shows up here rather than in a mock's expectations.

Every wait is event-driven and every elapsed bound is passed as zero (already expired), so no
test sleeps wall-clock.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- marking the record BRAIN_ACTIVE before entering the residency scope (rather than after the
  health gate passed) reddens the chaos suite's
  ``test_the_record_reaches_brain_active_only_once_the_deep_model_serves``;
- returning True from drain's timeout path reddens
  ``test_a_drain_that_times_out_aborts_before_anything_is_evicted``;
- skipping the ``active()`` precondition reddens
  ``test_a_second_concurrent_handoff_is_refused_without_evicting_anything``;
- dropping the ``escalation=None`` on the deep phase's context reddens
  ``test_the_deep_phase_cannot_escalate_to_itself``.
"""

import asyncio
import logging
from collections.abc import Sequence

import pytest
import swap_harness as harness
from swap_harness import Fakes, RecordingHandoffStore, ScriptedBrainBackend, build_harness

from cortex_core import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    DRAIN_TIMEOUT_NOTE,
    ESCALATE_TOOL_NAME,
    RESTORE_FAILED_NOTE,
    STORE_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    DispatchBudget,
    EscalateToBrainTool,
    EscalationSlot,
    HandoffState,
    HandoffStoreError,
    InMemoryToolRegistry,
    ModelHostState,
    RecordingAuditSink,
    RecordingConfirmer,
    ScriptedModelHost,
    StatusUpdate,
    SystemClock,
    TaintLedger,
    TextDelta,
    ToolCall,
    ToolDispatcher,
    TurnCapabilities,
    TurnEvent,
)
from cortex_core.composite import CompositeToolRegistry


def _texts(events: Sequence[TurnEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextDelta))


def _states(events: Sequence[TurnEvent]) -> list[str]:
    return [event.detail for event in events if isinstance(event, StatusUpdate)]


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
    # The user is told what the machine is doing through the whole window, in order.
    assert len(_states(events)) == 4


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
    assert spent.charge(3) is True
    ledger = TaintLedger()
    ledger.ingest_untrusted("see http://evil.test/x", source=None)
    live = build_harness()
    await live.seed_session()
    slot = harness.armed_slot(taint=ledger, budget=spent)
    await harness.run_handoff(live, slot)
    record = await live.handoffs.get(harness.TURN)
    assert record is None  # a clean handoff deletes it; the position rode the record
    # What the deep phase rebuilt is what the record carried: one dispatch left, and a ledger
    # that still knows the turn is tainted and which URL it laundered.
    resumed = DispatchBudget.resume(remaining=1, closed=False)
    assert (resumed.limit, resumed.spent, resumed.closed) == (1, 0, False)
    assert resumed.charge(1) is True
    assert resumed.charge(1) is False


async def test_a_closed_budget_stays_closed_across_the_swap() -> None:
    resumed = DispatchBudget.resume(remaining=0, closed=True)
    assert resumed.closed is True
    assert resumed.charge(1) is False


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
    assert [record.message for record in caplog.records] == ["refusing a second concurrent handoff"]


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
    assert not task.done()  # and the straggler was not killed
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
    assert live.scheduler.admitted == []
    assert live.handoffs.states[-1] is HandoffState.DONE


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


async def test_a_store_that_fails_while_settling_the_record_does_not_fail_the_turn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boot recovery is the backstop for a store that dies late, so the turn still converges."""

    class _FailsLate(RecordingHandoffStore):
        async def transition(self, handoff_id: str, state: HandoffState) -> bool:
            del handoff_id, state
            msg = "redis went away mid-handoff"
            raise HandoffStoreError(msg)

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


async def test_the_deep_phase_cannot_escalate_to_itself() -> None:
    """No slot rides the deep phase's dispatches, so a second handoff cannot be queued.

    The capabilities handed in even carry a slot, as a stream's bundle does; the phase must
    still stamp ``None`` onto its dispatches, or the deep model could escalate to itself and
    the wrapper would run a swap inside a swap.
    """
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
                tool_call=ToolCall(
                    id="c1", name=ESCALATE_TOOL_NAME, arguments={"brief": "go deeper still"}
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
