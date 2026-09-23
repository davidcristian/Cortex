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

# Every swap opens by asking which daemon is answering, which is the first thing the host is
# touched for and the last thing before anything is evicted.
_ASKED_WHO = (("boot_id", ""),)
_EVICTED = (*_ASKED_WHO, ("stop", "cortex"))
_SWAPPED_IN = (*_EVICTED, ("start", "brain"))
_SWAPPED_BACK = (*_SWAPPED_IN, ("stop", "brain"), ("start", "cortex"))

_LATER_TURN = "t-later"


def _texts(events: list[TurnEvent]) -> str:
    """Everything the turn's stream said, joined as the user would read it."""
    return "".join(event.text for event in events if isinstance(event, TextDelta))


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few times so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


class _PausingScheduler(WitnessingScheduler):
    """A pool that pauses the handoff during the drain, or once it has drained."""

    def __init__(self, *, mid: Gate | None = None, after: Gate | None = None) -> None:
        super().__init__()
        self.straggler: asyncio.Task[None] | None = None
        self._mid = mid
        self._after = after
        self._parked = asyncio.Event()

    @property
    def draining(self) -> bool:
        """Whether the pool is refusing admissions, as its own ``drain`` left it."""
        return self._draining

    async def drain(self, *, timeout_s: float) -> bool:
        if self._mid is not None:
            await self._park_a_straggler(self._mid)
        drained = await super().drain(timeout_s=timeout_s)
        if self._after is not None:
            await self._after.pause()
        return drained

    async def _park_a_straggler(self, gate: Gate) -> None:
        """Admit one request that outlives the start of the drain, and wait until it is held."""
        self.straggler = asyncio.create_task(self._park(gate))
        async with asyncio.timeout(5.0):
            await self._parked.wait()

    async def _park(self, gate: Gate) -> None:
        """The request admitted first, which then holds the drain open at the pause point."""
        async with self.admit(harness.request()):
            self._parked.set()
            await self._the_pool_closes_around_it()
            await gate.pause()

    async def _the_pool_closes_around_it(self) -> None:
        """Wait for the pool's own ``drain`` to stop admitting, this request still running."""
        async with self._pool:
            while not self._draining:
                await self._pool.wait()


class _YieldingHandoffStore(RecordingHandoffStore):
    """A store whose methods suspend, as a real network store does and an in-memory one does not."""

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
    """Run one handoff, collecting its events. This is the task a failure case cancels."""
    stream = live.conductor.run_handoff(
        harness.armed_slot(), session_id=harness.SESSION, turn_id=turn_id
    )
    try:
        async for event in stream:
            events.append(live.observe(event))  # noqa: PERF401 - a live stream, one at a time
    finally:
        await stream.aclose()


async def _admit(live: Harness) -> None:
    """One subagent admission, so a refusal can be checked without leaving a block open."""
    async with live.scheduler.admit(harness.request()):
        pass


async def assert_converged_on_cortex(live: Harness) -> None:
    """The cortex is resident again and the subagent pool admits again."""
    if ("stop", live.residency.cortex_model) in live.host.calls:
        assert ("start", live.residency.cortex_model) in live.host.calls
    usual = {live.residency.cortex_model, *live.residency.evict_models}
    assert live.host.running == usual
    assert live.host.calls.count(("start", live.residency.brain_model)) <= 1
    assert live.backend.calls <= 1
    if live.scheduler.drains:
        assert live.scheduler.reopened
    assert all(running == usual for running in live.scheduler.reopened)
    await _admit(live)


async def assert_stores_intact(
    live: Harness,
    *,
    deep_reply: str | None = None,
    killed: bool = False,
    settled: bool = True,
) -> None:
    """Nothing either phase saved is lost, and no handoff is left running."""
    assert await live.handoffs.active() is None
    record = await live.handoffs.get(harness.TURN)
    assert record is None or record.state.terminal
    if record is not None and record.state is HandoffState.FAILED:
        assert record.failure
    assert live.handoffs.states
    if settled:
        assert live.handoffs.states[-1].terminal
    else:
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


def assert_stream_reported_only_real_progress(
    live: Harness, events: list[TurnEvent], *, killed: bool
) -> None:
    """No event reported progress that had not been made."""
    details: list[str] = []
    for event in events:
        assert isinstance(event, StatusUpdate | TextDelta)
        if isinstance(event, StatusUpdate):
            assert event.state == SWAPPING_STATE
            details.append(event.detail)
    assert [witness.detail for witness in live.statuses] == details
    assert_the_window_announced_real_progress(live)
    if not killed:
        assert any(isinstance(event, TextDelta) for event in events)


async def assert_the_next_turn_still_works(live: Harness) -> None:
    """The next turn can run: the cortex is leased again, without waiting."""
    async with asyncio.timeout(5.0), live.manager.acquire(live.residency.cortex_model) as lease:
        assert lease.endpoint == harness.CORTEX_URL


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
    del case  # named for the parametrize id
    live = make()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply)
    assert_stream_reported_only_real_progress(live, events, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_a_drain_that_times_out_converges_without_evicting_anything() -> None:
    live = build_harness(residency=harness.plan(drain_timeout_s=0.0))
    await live.seed_session()
    held = Gate()

    async def in_flight() -> None:
        async with live.scheduler.admit(harness.request()):
            await held.pause()

    task = asyncio.create_task(in_flight())
    await held.arrived()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert live.host.calls == harness.PREFLIGHT_CALLS
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live)
    assert_stream_reported_only_real_progress(live, events, killed=False)
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
    del case  # named for the parametrize id
    live = make()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply, settled=False)
    assert_stream_reported_only_real_progress(live, events, killed=False)
    await assert_the_next_turn_still_works(live)

    later = await harness.run_handoff(live, harness.armed_slot(), turn_id=_LATER_TURN)
    assert _texts(later) == later_text
    assert await live.handoffs.active() is None
    stranded = await live.handoffs.get(_LATER_TURN)
    assert stranded is None or stranded.state.terminal
    assert live.host.running == {"cortex"}
    await _admit(live)


def _after_snapshot(gate: Gate) -> Harness:
    return build_harness(Fakes(handoffs=RecordingHandoffStore(put_gate=gate)))


def _mid_drain(gate: Gate) -> Harness:
    return build_harness(scheduler=_PausingScheduler(mid=gate))


def _after_drain(gate: Gate) -> Harness:
    return build_harness(scheduler=_PausingScheduler(after=gate))


def _arm(host: ScriptedModelHost, op: str, model: str, gate: Gate) -> None:
    """Make one host operation pause at this test's own pause point."""
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
    del case  # named for the parametrize id
    gate = Gate()
    live = make(gate)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    assert [call for call in live.host.calls if call[0] != "status"] == list(host_touched)
    task.cancel()
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply, killed=True)
    torn_down = await live.handoffs.get(harness.TURN)
    assert torn_down is not None
    assert torn_down.failure == TORN_DOWN_REASON
    assert_stream_reported_only_real_progress(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_the_mid_drain_kill_arrives_while_the_pool_is_actually_quiescing() -> None:
    gate = Gate()
    scheduler = _PausingScheduler(mid=gate)
    live = build_harness(scheduler=scheduler)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    assert scheduler.straggler is not None
    assert not scheduler.straggler.done()
    assert scheduler.draining is True
    with pytest.raises(SubagentAdmissionError):
        await _admit(live)
    assert live.handoffs.states == [HandoffState.READY]
    assert live.host.calls == harness.PREFLIGHT_CALLS
    task.cancel()
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)


async def test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched() -> None:
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
    winner = asyncio.create_task(_consume(live, won))
    loser = asyncio.create_task(_consume(live, lost, turn_id="t-loser"))
    await put_gate.arrived()
    await _settle()

    assert loser.done()
    await loser
    assert lost == [TextDelta(text=ALREADY_ACTIVE_NOTE)]
    assert await live.handoffs.get("t-loser") is None
    put_gate.release.set()
    await working.arrived()
    with pytest.raises(SubagentAdmissionError):
        await _admit(live)
    working.release.set()
    await winner

    assert live.host.calls.count(("start", "brain")) == 1
    assert live.backend.calls == 1
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_reported_only_real_progress(live, won, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_closing_the_stream_mid_handoff_unwinds_the_swap_rather_than_abandoning_it() -> None:
    live = build_harness()
    await live.seed_session()
    stream = live.conductor.run_handoff(
        harness.armed_slot(), session_id=harness.SESSION, turn_id=harness.TURN
    )
    events: list[TurnEvent] = []
    async for event in stream:
        events.append(live.observe(event))
        if isinstance(event, TextDelta):
            break
    assert live.host.running == {"brain"}
    assert live.backend.closed is False
    await stream.aclose()
    assert live.host.running == {"cortex"}
    assert live.backend.closed is True
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, killed=True)
    assert_stream_reported_only_real_progress(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_a_second_cancellation_during_the_swap_back_still_holds_the_drain_window_shut() -> (
    None
):
    gate = Gate()
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    _arm(host, "start", "cortex", gate)
    live = build_harness(Fakes(host=host), residency=harness.plan(evict_models=("subagent-gpu",)))
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    assert live.host.running == {"cortex"}
    task.cancel()
    await _settle()
    task.cancel()
    await _settle()
    assert not live.scheduler.reopened
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer", killed=True)
    assert_stream_reported_only_real_progress(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_a_tier_evicted_for_the_handoff_is_running_again_when_it_ends() -> None:
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    live = build_harness(Fakes(host=host), residency=harness.plan(evict_models=("subagent-gpu",)))
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    assert ("stop", "subagent-gpu") in host.calls
    assert host.running == {"cortex", "subagent-gpu"}
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_reported_only_real_progress(live, events, killed=False)
    await assert_the_next_turn_still_works(live)


async def test_taint_and_its_evidence_survive_the_swap_and_still_bind_the_deep_model() -> None:
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
    assert shown
    assert "http://evil.test/x" not in shown
    persisted = [message.text for message in await live.sessions.history(harness.SESSION)]
    assert "http://evil.test/x" not in persisted[-1]
    assert await live.remembered() == []
    await assert_converged_on_cortex(live)
    await assert_the_next_turn_still_works(live)


async def test_the_swap_waits_for_an_in_flight_cortex_round_to_fall_free() -> None:
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
    assert live.host.calls == harness.PREFLIGHT_CALLS
    release.set()
    await round_task
    await handoff
    assert ("stop", "cortex") in live.host.calls
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
    assert_stream_reported_only_real_progress(live, events, killed=False)


async def test_the_record_reaches_brain_active_only_once_the_deep_model_serves() -> None:
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
    assert live.backend.calls == 0


async def test_boot_recovery_fails_a_stranded_record_and_lets_the_next_handoff_run() -> None:
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
        live.manager.baseline_tiers,
        clock=harness.TickingClock(),
        sleeper=RecordingSleeper(),
    )

    assert await live.handoffs.active() is None
    failed = await live.handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED
    assert failed.failure == STRANDED_REASON
    assert host.running == {"cortex"}
    await assert_the_next_turn_still_works(live)

    later = await harness.run_handoff(live, harness.armed_slot())
    assert _texts(later) == "a deep answer"
    assert live.backend.calls == 1
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply="a deep answer")
