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
    build_harness,
)

from cortex_core import (
    BRAIN_FAILED_NOTE,
    SWAPPING_STATE,
    AdmitAllScheduler,
    HandoffState,
    ModelHostState,
    RecordingSleeper,
    ScriptedModelHost,
    StatusUpdate,
    TextDelta,
    TurnEvent,
    recover_handoffs,
)

# How far the host has been driven at each boundary, ignoring readiness polls: the eviction, the
# swap in, and the whole way back. Naming them keeps each case's expectation readable.
_EVICTED = (("stop", "cortex"),)
_SWAPPED_IN = (*_EVICTED, ("start", "brain"))
_SWAPPED_BACK = (*_SWAPPED_IN, ("stop", "brain"), ("start", "cortex"))


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few turns so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


class _PausingScheduler(AdmitAllScheduler):
    """A pool that pauses the handoff at a drain boundary: while draining, or once drained."""

    def __init__(self, *, mid: Gate | None = None, after: Gate | None = None) -> None:
        super().__init__()
        self._mid = mid
        self._after = after

    async def drain(self, *, timeout_s: float) -> bool:
        if self._mid is not None:
            await self._mid.pause()
        drained = await super().drain(timeout_s=timeout_s)
        if self._after is not None:
            await self._after.pause()
        return drained


async def _consume(live: Harness, events: list[TurnEvent]) -> None:
    """Run one handoff, collecting its events; the task a chaos case cancels."""
    stream = live.conductor.run_handoff(
        harness.armed_slot(), session_id=harness.SESSION, turn_id=harness.TURN
    )
    try:
        async for event in stream:
            events.append(event)  # noqa: PERF401 - a live stream, read one event at a time
    finally:
        await stream.aclose()


async def assert_converged_on_cortex(live: Harness) -> None:
    """Invariants 1 and 2: the cortex serves again and the subagent pool admits again."""
    if ("stop", live.residency.cortex_model) in live.host.calls:
        # Anything that evicted the cortex owes the restore; the scope's finally is what pays.
        assert ("start", live.residency.cortex_model) in live.host.calls
    assert live.host.running == {live.residency.cortex_model}
    assert live.host.calls.count(("start", live.residency.brain_model)) <= 1  # nothing double-ran
    assert live.backend.calls <= 1  # the deep model answered at most once
    async with live.scheduler.admit(harness.request()):
        pass


async def assert_stores_intact(live: Harness, *, deep_reply: str | None = None) -> None:
    """Invariant 3: nothing the cortex phase persisted is lost, and no handoff stays live."""
    assert await live.handoffs.active() is None
    record = await live.handoffs.get(harness.TURN)
    assert record is None or record.state.terminal
    assert live.handoffs.states  # the record existed at all
    assert live.handoffs.states[-1].terminal  # and its last written state ended it
    history = [
        (message.role.value, message.text)
        for message in await live.sessions.history(harness.SESSION)
    ]
    expected = [("user", harness.USER_TEXT), ("assistant", harness.CORTEX_TEXT)]
    if deep_reply is not None:
        expected.append(("assistant", deep_reply))
    assert history == expected


def assert_stream_ended_honestly(events: list[TurnEvent], *, killed: bool) -> None:
    """Invariant 4: nothing on the stream claimed more than the machine actually did."""
    for event in events:
        assert isinstance(event, StatusUpdate | TextDelta)
        if isinstance(event, StatusUpdate):
            assert event.state == SWAPPING_STATE
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
    assert_stream_ended_honestly(events, killed=False)
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
    assert live.host.calls == []  # the whole point: nothing was evicted
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live)
    assert_stream_ended_honestly(events, killed=False)
    held.release.set()
    await task


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
    await assert_stores_intact(live, deep_reply=deep_reply)
    assert_stream_ended_honestly(events, killed=True)
    await assert_the_next_turn_still_works(live)


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


async def test_boot_recovery_fails_a_stranded_record_and_converges_without_double_running() -> None:
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
        clock=harness.TickingClock(),
        sleeper=RecordingSleeper(),
    )

    assert await live.handoffs.active() is None
    failed = await live.handoffs.get(harness.TURN)
    assert failed is not None
    assert failed.state is HandoffState.FAILED
    assert host.running == {"cortex"}
    assert live.backend.calls == 0  # nothing was resumed, so nothing double-ran
    assert [m.text for m in await live.sessions.history(harness.SESSION)] == [
        harness.USER_TEXT,
        harness.CORTEX_TEXT,
    ]
    await assert_the_next_turn_still_works(live)
