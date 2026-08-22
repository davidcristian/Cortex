"""THE chaos suite: kill the handoff at every step boundary, and prove it always converges."""

import asyncio
from collections.abc import Callable

import pytest
import swap_harness as harness
from swap_harness import (
    Fakes,
    Gate,
    Harness,
    RecordingHandoffStore,
    RecordingSessionStore,
    ScriptedBrainBackend,
    WitnessingScheduler,
    assert_the_window_announced_real_progress,
    build_harness,
)

from cortex_core import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    STRANDED_REASON,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
    TORN_DOWN_REASON,
    HandoffRecord,
    HandoffState,
    ModelHostState,
    RecordingSleeper,
    ScriptedModelHost,
    SourceKind,
    StatusUpdate,
    SubagentAdmissionError,
    TaintLedger,
    TextDelta,
    TurnCapabilities,
    TurnEvent,
    UrlRedactingGuardrail,
    as_source,
    recover_handoffs,
    render_exchange,
)

_ASKED_WHO = (("boot_id", ""),)
_EVICTED = (*_ASKED_WHO, ("stop", "cortex"))
_SWAPPED_IN = (*_EVICTED, ("start", "brain"))
_SWAPPED_BACK = (*_SWAPPED_IN, ("stop", "brain"), ("start", "cortex"))

# The turn id of the escalation that comes AFTER a broken one, which is what proves a handoff
# the store could not settle did not wedge the escalation path for the rest of the process.
_LATER_TURN = "t-later"


def _texts(events: list[TurnEvent]) -> str:
    """Everything the turn's stream actually said, as the user would read it."""
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few turns so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


class _PausingScheduler(WitnessingScheduler):
    """A pool that pauses the handoff at a drain boundary: inside the window, or once drained."""

    def __init__(self, *, mid: Gate | None = None, after: Gate | None = None) -> None:
        super().__init__()
        self.straggler: asyncio.Task[None] | None = None
        self._mid = mid
        self._after = after
        self._parked = asyncio.Event()

    @property
    def draining(self) -> bool:
        """Whether the refusal window is open, as the pool's own ``drain`` left it."""
        return self._draining

    async def drain(self, *, timeout_s: float) -> bool:
        if self._mid is not None:
            await self._park_a_straggler(self._mid)
        drained = await super().drain(timeout_s=timeout_s)
        if self._after is not None:
            await self._after.pause()
        return drained

    async def _park_a_straggler(self, gate: Gate) -> None:
        """Admit one request that will outlive the window's opening, and wait until it holds."""
        self.straggler = asyncio.create_task(self._park(gate))
        async with asyncio.timeout(5.0):
            await self._parked.wait()

    async def _park(self, gate: Gate) -> None:
        """The straggler: admitted first, then holding the drain open at the gate."""
        async with self.admit(harness.request()):
            self._parked.set()
            await self._the_pool_closes_around_it()
            await gate.pause()

    async def _the_pool_closes_around_it(self) -> None:
        """Wait for the pool's own ``drain`` to shut admission with this request still in flight."""
        async with self._pool:
            while not self._draining:
                await self._pool.wait()


class _YieldingHandoffStore(RecordingHandoffStore):
    """A store whose verbs suspend, as a real network store's do; the in-memory twin never does."""

    def __init__(self, *, hold_first_put: Gate | None = None) -> None:
        super().__init__()
        self._hold_first_put = hold_first_put

    async def active(self) -> HandoffRecord | None:
        await asyncio.sleep(0)
        return await super().active()

    async def put(self, record: HandoffRecord) -> None:
        gate, self._hold_first_put = self._hold_first_put, None
        if gate is not None:
            await gate.pause()
        await super().put(record)


async def _consume(live: Harness, events: list[TurnEvent], *, turn_id: str = harness.TURN) -> None:
    """Run one handoff, collecting its events; the task a chaos case cancels."""
    stream = live.conductor.run_handoff(
        harness.armed_slot(), session_id=harness.SESSION, turn_id=turn_id
    )
    try:
        async for event in stream:
            events.append(live.observe(event))  # noqa: PERF401 - a live stream, one at a time
    finally:
        await stream.aclose()


async def _admit(live: Harness) -> None:
    """One subagent admission, so a refusal can be asserted without leaving a block hanging."""
    async with live.scheduler.admit(harness.request()):
        pass


async def assert_converged_on_cortex(live: Harness) -> None:
    """Invariants 1 and 2: the standing residency is back and the pool admits again."""
    if ("stop", live.residency.cortex_model) in live.host.calls:
        # Anything that evicted the cortex owes the restore; the scope's finally is what pays.
        assert ("start", live.residency.cortex_model) in live.host.calls
    standing = {live.residency.cortex_model, *live.residency.evict_models}
    assert live.host.running == standing
    assert live.host.calls.count(("start", live.residency.brain_model)) <= 1  # nothing double-ran
    assert live.backend.calls <= 1  # the deep model answered at most once
    if live.scheduler.drains:  # a handoff torn down before the drain never opened a window
        assert live.scheduler.reopened
    assert all(running == standing for running in live.scheduler.reopened)
    await _admit(live)


async def assert_stores_intact(
    live: Harness,
    *,
    deep_reply: str | None = None,
    killed: bool = False,
    settled: bool = True,
) -> None:
    """Invariant 3: nothing either phase persisted is lost, and no handoff stays live."""
    assert await live.handoffs.active() is None
    record = await live.handoffs.get(harness.TURN)
    assert record is None or record.state.terminal
    if record is not None and record.state is HandoffState.FAILED:
        assert record.failure
    assert live.handoffs.states  # the record existed at all
    if settled:
        assert live.handoffs.states[-1].terminal  # and its last written state ended it
    else:
        # ``settled=False`` is the store that refused the settling write itself, so no terminal
        # state could ever be written. What the conductor owes there is the stronger thing: the
        # record is GONE, so nothing can go on reading it as a handoff still in flight.
        assert record is None
        assert live.handoffs.deleted == [harness.TURN]
    history = [
        (message.role.value, message.text)
        for message in await live.sessions.history(harness.SESSION)
    ]
    expected = [("user", harness.USER_TEXT), ("assistant", harness.CORTEX_TEXT)]
    if deep_reply is not None:
        expected.append(("assistant", deep_reply))
    assert history == expected
    remembered = [memory.text for memory in await live.remembered()]
    written = [] if deep_reply is None else [render_exchange(harness.USER_TEXT, deep_reply)]
    if killed:
        assert remembered in ([], written)
    else:
        assert remembered == written


def assert_stream_ended_honestly(live: Harness, events: list[TurnEvent], *, killed: bool) -> None:
    """Invariant 4: no event claimed progress the machine had not actually made."""
    details: list[str] = []
    for event in events:
        assert isinstance(event, StatusUpdate | TextDelta)
        if isinstance(event, StatusUpdate):
            assert event.state == SWAPPING_STATE
            details.append(event.detail)
    # The witnesses are what the assertions below run on, so they must be this stream's own.
    assert [witness.detail for witness in live.statuses] == details
    assert_the_window_announced_real_progress(live)
    if not killed:
        assert any(isinstance(event, TextDelta) for event in events)


async def assert_the_next_turn_still_works(live: Harness) -> None:
    """A converged system is one the next turn can use: the cortex leases again, at once."""
    async with asyncio.timeout(5.0), live.manager.acquire(live.residency.cortex_model) as lease:
        assert lease.endpoint == harness.CORTEX_URL


# ---------------------------------------------------------------------------------------------
# The scripted-failure kill points: the conductor's own error paths, with nothing cancelled.
# ---------------------------------------------------------------------------------------------


def _brain_start_fails() -> Harness:
    return build_harness(
        Fakes(host=ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM"}))
    )


def _health_gate_times_out() -> Harness:
    return build_harness(
        Fakes(
            host=ScriptedModelHost(
                running=["cortex"], status_override={"brain": ModelHostState.LOADING}
            )
        ),
        residency=harness.plan(load_timeout_s=0.0),
    )


def _cortex_restore_fails_once() -> Harness:
    return build_harness(
        Fakes(host=ScriptedModelHost(running=["cortex"], fail_once={("start", "cortex"): "busy"}))
    )


def _brain_dies_mid_answer() -> Harness:
    return build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("half an ", "never streamed"), fail_after=1))
    )


@pytest.mark.parametrize(
    ("case", "make", "deep_reply"),
    [
        ("brain-start-fails", _brain_start_fails, None),
        ("health-gate-times-out", _health_gate_times_out, None),
        ("cortex-restore-fails-once", _cortex_restore_fails_once, "a deep answer"),
        ("mid-brain-stream-server-death", _brain_dies_mid_answer, "half an " + BRAIN_FAILED_NOTE),
    ],
)
async def test_a_scripted_failure_converges_and_tells_the_user(
    case: str, make: Callable[[], Harness], deep_reply: str | None
) -> None:
    """Every scripted way a swap can break: the cortex is back and the turn ends honestly."""
    del case  # named for the parametrize id, which is the ADR's own kill-point name
    live = make()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply)
    assert_stream_ended_honestly(live, events, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_a_drain_that_times_out_converges_without_evicting_anything() -> None:
    """The abort-before-eviction branch, held open by an admission that never releases in time."""
    live = build_harness(residency=harness.plan(drain_timeout_s=0.0))
    await live.seed_session()
    held = Gate()

    async def in_flight() -> None:
        async with live.scheduler.admit(harness.request()):
            await held.pause()

    task = asyncio.create_task(in_flight())
    await held.arrived()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert live.host.calls == harness.PREFLIGHT_CALLS  # the whole point: nothing was evicted
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live)
    assert_stream_ended_honestly(live, events, killed=False)
    await assert_the_next_turn_still_works(live)
    assert not task.done()
    held.release.set()
    await task


def _settle_of_a_clean_handoff_is_refused() -> Harness:
    return build_harness(Fakes(handoffs=RecordingHandoffStore(fail_settle=HandoffState.DONE)))


def _settle_of_an_aborted_handoff_is_refused() -> Harness:
    return build_harness(
        Fakes(
            host=ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM"}),
            handoffs=RecordingHandoffStore(fail_settle=HandoffState.FAILED),
        )
    )


@pytest.mark.parametrize(
    ("case", "make", "deep_reply", "later_text"),
    [
        (
            "settle-done-refused",
            _settle_of_a_clean_handoff_is_refused,
            "a deep answer",
            "a deep answer",
        ),
        ("settle-failed-refused", _settle_of_an_aborted_handoff_is_refused, None, SWAP_FAILED_NOTE),
    ],
)
async def test_a_store_that_refuses_the_settling_write_still_frees_the_next_handoff(
    case: str, make: Callable[[], Harness], deep_reply: str | None, later_text: str
) -> None:
    """The kill point the suite had at no boundary at all: the store, on the write that ends it."""
    del case  # named for the parametrize id
    live = make()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply, settled=False)
    assert_stream_ended_honestly(live, events, killed=False)
    await assert_the_next_turn_still_works(live)

    later = await harness.run_handoff(live, harness.armed_slot(), turn_id=_LATER_TURN)
    assert _texts(later) == later_text
    assert await live.handoffs.active() is None
    stranded = await live.handoffs.get(_LATER_TURN)
    assert stranded is None or stranded.state.terminal
    assert live.host.running == {"cortex"}
    await _admit(live)


# ---------------------------------------------------------------------------------------------
# The cancellation kill points: the process-death analogue, at every boundary of the sequence.
# ---------------------------------------------------------------------------------------------


def _after_snapshot(gate: Gate) -> Harness:
    return build_harness(Fakes(handoffs=RecordingHandoffStore(put_gate=gate)))


def _mid_drain(gate: Gate) -> Harness:
    return build_harness(scheduler=_PausingScheduler(mid=gate))


def _after_drain(gate: Gate) -> Harness:
    return build_harness(scheduler=_PausingScheduler(after=gate))


def _arm(host: ScriptedModelHost, op: str, model: str, gate: Gate) -> None:
    """Arm one host operation's boundary with this test's gate (the fake's own pause hooks)."""
    host.reached[(op, model)] = gate.reached
    host.release[(op, model)] = gate.release


def _after_cortex_stop(gate: Gate) -> Harness:
    host = ScriptedModelHost(running=["cortex"])
    _arm(host, "stop", "cortex", gate)
    return build_harness(Fakes(host=host))


def _mid_brain_stream(gate: Gate) -> Harness:
    return build_harness(Fakes(backend=ScriptedBrainBackend(gate=gate, gate_after=1)))


def _after_brain_persist(gate: Gate) -> Harness:
    return build_harness(Fakes(sessions=RecordingSessionStore(append_gate=gate, gate_after=3)))


def _during_swap_back(gate: Gate) -> Harness:
    host = ScriptedModelHost(running=["cortex"])
    _arm(host, "start", "cortex", gate)
    return build_harness(Fakes(host=host))


@pytest.mark.parametrize(
    ("case", "make", "host_touched", "deep_reply"),
    [
        ("after-snapshot", _after_snapshot, (), None),
        ("mid-drain", _mid_drain, (), None),
        ("after-drain", _after_drain, (), None),
        ("after-cortex-stop", _after_cortex_stop, _EVICTED, None),
        ("mid-brain-stream", _mid_brain_stream, _SWAPPED_IN, None),
        ("after-brain-persist", _after_brain_persist, _SWAPPED_IN, "a deep answer"),
        ("during-swap-back", _during_swap_back, _SWAPPED_BACK, "a deep answer"),
    ],
)
async def test_a_kill_at_a_step_boundary_converges_back_onto_the_cortex(
    case: str,
    make: Callable[[Gate], Harness],
    host_touched: tuple[tuple[str, str], ...],
    deep_reply: str | None,
) -> None:
    """Cancel the handoff exactly at this boundary; the system must land where it started."""
    del case  # named for the parametrize id, which is the ADR's own kill-point name
    gate = Gate()
    live = make(gate)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    # The boundary really is where its name says: exactly this much has happened to the host.
    assert [call for call in live.host.calls if call[0] != "status"] == list(host_touched)
    task.cancel()
    gate.release.set()  # the paused operation completes or unwinds; the kill lands either way
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply, killed=True)
    # And it says which of the failures it was. A kill is the one that says nothing about the
    # machine (nothing refused anything; the sequence simply stopped being run), so the record
    # must not describe it as a swap that broke.
    torn_down = await live.handoffs.get(harness.TURN)
    assert torn_down is not None
    assert torn_down.failure == TORN_DOWN_REASON
    assert_stream_ended_honestly(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_the_mid_drain_kill_lands_while_the_pool_is_actually_quiescing() -> None:
    """The mid-drain boundary is a different system state from after-snapshot, and this pins it."""
    gate = Gate()
    scheduler = _PausingScheduler(mid=gate)
    live = build_harness(scheduler=scheduler)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    assert scheduler.straggler is not None  # the premise, restated so the boundary cannot
    assert not scheduler.straggler.done()  # degrade unnoticed into a drained-pool pause
    assert scheduler.draining is True  # the refusal window is open
    with pytest.raises(SubagentAdmissionError):
        await _admit(live)
    # And the pool was touched only once the handoff was safe to abandon: the record is written
    # and READY before the drain begins, so a kill here costs a handoff and nothing else.
    assert live.handoffs.states == [HandoffState.READY]
    assert live.host.calls == harness.PREFLIGHT_CALLS  # while nothing at all was evicted
    task.cancel()
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)


async def test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched() -> None:
    """One GPU means one handoff, and the loser must not have run the prologue at all."""
    put_gate, working = Gate(), Gate()
    live = build_harness(
        Fakes(
            handoffs=_YieldingHandoffStore(hold_first_put=put_gate),
            backend=ScriptedBrainBackend(gate=working, gate_after=1),
        )
    )
    await live.seed_session()
    won: list[TurnEvent] = []
    lost: list[TurnEvent] = []
    # Both turns are started before either can finish claiming, which is the interleaving that
    # matters: a claim read in one step and taken in another would let both of them through.
    winner = asyncio.create_task(_consume(live, won))
    loser = asyncio.create_task(_consume(live, lost, turn_id="t-loser"))
    await put_gate.arrived()  # the winner is between its own check and its first write
    await _settle()

    assert loser.done()  # refused at once, with nothing to wait for
    await loser
    assert lost == [TextDelta(text=ALREADY_ACTIVE_NOTE)]
    assert await live.handoffs.get("t-loser") is None  # it never even wrote a record
    put_gate.release.set()
    await working.arrived()
    # With the winner mid handoff the drain window is still shut. This is the assertion the
    # defect broke: the loser's own ``finally`` reopened it under the resident deep model.
    with pytest.raises(SubagentAdmissionError):
        await _admit(live)
    working.release.set()
    await winner

    assert live.host.calls.count(("start", "brain")) == 1
    assert live.backend.calls == 1
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_ended_honestly(live, won, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_closing_the_stream_mid_handoff_unwinds_the_swap_rather_than_abandoning_it() -> None:
    """A consumer that walks away is not a cancellation, and it must converge just the same."""
    live = build_harness()
    await live.seed_session()
    stream = live.conductor.run_handoff(
        harness.armed_slot(), session_id=harness.SESSION, turn_id=harness.TURN
    )
    events: list[TurnEvent] = []
    async for event in stream:
        events.append(live.observe(event))
        if isinstance(event, TextDelta):
            break  # the deep model is mid-answer: its round is open and so is the scope
    assert live.host.running == {"brain"}  # the swap really is in flight
    assert live.backend.closed is False
    await stream.aclose()
    # No settling and no cancellation: closing the stream is itself what owes the swap back,
    # the deep model's round, and (only once both are done) the drain window.
    assert live.host.running == {"cortex"}
    assert live.backend.closed is True  # the innermost teardown, which nothing else can see
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, killed=True)
    assert_stream_ended_honestly(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_a_second_cancellation_during_the_swap_back_still_holds_the_drain_window_shut() -> (
    None
):
    """Two cancellations, which is what the seam actually delivers, must not free the pool early."""
    gate = Gate()
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    _arm(host, "start", "cortex", gate)  # the swap back, held open mid-restore
    live = build_harness(Fakes(host=host), residency=harness.plan(evict_models=("subagent-gpu",)))
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    # Mid-restore: the deep model is gone, the cortex is coming up, the tier is still stopped
    # (it is started back only after the cortex gates ready).
    assert live.host.running == {"cortex"}
    task.cancel()
    await _settle()  # the first cancellation reaches the shielded wait
    task.cancel()  # and here comes the one that used to abandon it
    await _settle()
    assert not live.scheduler.reopened  # nothing may have reopened while the GPU is empty
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer", killed=True)
    assert_stream_ended_honestly(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_a_tier_evicted_for_the_handoff_is_running_again_when_it_ends() -> None:
    """Convergence means the standing residency, not the cortex alone."""
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    live = build_harness(Fakes(host=host), residency=harness.plan(evict_models=("subagent-gpu",)))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert ("stop", "subagent-gpu") in host.calls  # it really was evicted for the deep model
    assert host.running == {"cortex", "subagent-gpu"}
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_ended_honestly(live, events, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_taint_and_its_evidence_survive_the_swap_and_still_bind_the_deep_model() -> None:
    """The other half of the hard rule, inside the artifact that claims to prove it end to end."""
    ledger = TaintLedger()
    ledger.ingest_untrusted(
        "read http://evil.test/x", source=as_source(SourceKind.TOOL, "read_page")
    )
    live = build_harness(
        Fakes(backend=ScriptedBrainBackend(chunks=("visit http://evil.test/x now",))),
        capabilities=TurnCapabilities(guardrail=UrlRedactingGuardrail()),
    )
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot(taint=ledger))
    shown = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert shown  # it did answer; the redaction below is not just an empty stream
    # The guardrail on the far side opened over the RECORD's evidence, not a fresh empty set.
    assert "http://evil.test/x" not in shown
    persisted = [message.text for message in await live.sessions.history(harness.SESSION)]
    assert "http://evil.test/x" not in persisted[-1]
    # And the same taint policy the cortex phase applies kept it out of durable memory.
    assert await live.remembered() == []
    await assert_converged_on_cortex(live)
    await assert_the_next_turn_still_works(live)


async def test_the_swap_waits_for_an_in_flight_cortex_round_to_fall_free() -> None:
    """Swaps happen only at lease-free boundaries, which the end-to-end artifact owes too.

    v1 never preempts a round in flight, so a handoff that starts while the cortex is
    mid-answer on another stream evicts nothing at all until that round releases the GPU.
    """
    live = build_harness()
    await live.seed_session()
    holding, release = asyncio.Event(), asyncio.Event()

    async def in_flight_round() -> None:
        async with live.manager.acquire(live.residency.cortex_model):
            holding.set()
            await release.wait()

    round_task = asyncio.create_task(in_flight_round())
    async with asyncio.timeout(5.0):
        await holding.wait()
    events: list[TurnEvent] = []
    handoff = asyncio.create_task(_consume(live, events))
    await _settle()
    assert live.host.calls == harness.PREFLIGHT_CALLS  # queued behind the round, not preempting it
    release.set()
    await round_task
    await handoff
    assert ("stop", "cortex") in live.host.calls
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_ended_honestly(live, events, killed=False)


async def test_the_record_reaches_brain_active_only_once_the_deep_model_serves() -> None:
    """A kill before the health gate must never leave a record claiming the deep model ran."""
    gate = Gate()
    live = _after_cortex_stop(gate)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    task.cancel()
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert live.handoffs.states == [HandoffState.READY, HandoffState.FAILED]
    assert live.backend.calls == 0  # and the deep model was never asked anything


async def test_boot_recovery_fails_a_stranded_record_and_lets_the_next_handoff_run() -> None:
    """The kill no conductor can clean up after: the process itself died mid-handoff."""
    host = ScriptedModelHost(running=["brain"])
    live = build_harness(Fakes(host=host))
    await live.seed_session()
    stranded = harness.armed_slot().snapshot(
        turn_id=harness.TURN, session_id=harness.SESSION, requested_at=harness.TickingClock().now()
    )
    await live.handoffs.put(stranded)
    await live.handoffs.transition(harness.TURN, HandoffState.BRAIN_ACTIVE)
    assert await live.handoffs.active() is not None

    await recover_handoffs(
        live.handoffs,
        host,
        live.residency,
        live.manager.standing_tiers,
        clock=harness.TickingClock(),
        sleeper=RecordingSleeper(),
    )

    assert await live.handoffs.active() is None
    failed = await live.handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED
    # And it says which failure it was, which on this path is the only reader's only chance:
    # the process that ran the handoff is gone, so its log is a different container's history.
    assert failed.failure == STRANDED_REASON
    assert host.running == {"cortex"}
    await assert_the_next_turn_still_works(live)

    # Escalating again is the same turn's user asking again, so it carries the same id: the
    # FAILED record recovery left as its diagnosis must not refuse the retry of the very turn
    # it describes, which is the wedge a record kept but never settled would cause.
    later = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(later) == "a deep answer"
    assert live.backend.calls == 1  # asked once, by this turn, and never by recovery
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
