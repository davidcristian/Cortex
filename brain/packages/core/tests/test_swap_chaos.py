"""THE chaos suite: kill the handoff at every step boundary, and prove it always converges.

This is the CI half of ADR-0030 decision 7 and the gate the one hard rule is proven by. The
same real composition the conductor suite drives (real conductor, real residency manager, real
drain, real deep phase, over the scripted host and in-memory stores) is killed at each boundary
of the swap sequence, and every case asserts the same four invariants:

1. **the cortex serves again**: the exit path asked for it back whenever anything was evicted,
   and the host ends with the cortex as its only running model;
2. **the pool admits again**: the drain window is released whatever ended the handoff;
3. **the stores are intact**: the user message and the cortex's reply are still there, no
   partial deep answer is persisted as a completed one, no handoff is left live, and the record
   reached a terminal state (which a clean handoff then deletes, so it is the write log that
   proves it);
4. **the stream ended honestly**: the events say what happened, and the next turn still works.

Two kinds of kill, both from the ADR's list. A **scripted failure** (a host that refuses, a
model that never loads, a server that dies mid-answer) exercises the conductor's own error
paths. A **cancellation** at an armed boundary is the process-death analogue on the consumer
side: the task running the handoff is cancelled exactly there, which is what a killed turn, a
disconnected client, or a stopped stream does.

Determinism: every boundary is an ``asyncio.Event`` pair, every elapsed bound is passed as zero
(already expired), and ``_settle`` yields the loop a few turns. No test sleeps wall-clock.

Distrust-green proofs (each mutation was applied alone, reddened exactly the cases named, and
was then restored):
- restoring the cortex only on the scope's success path (no ``finally``) reddens
  ``after-cortex-stop``, ``mid-brain-stream`` and ``after-brain-persist`` here, plus every
  scripted-failure case in the conductor suite;
- moving the record's BRAIN_ACTIVE transition ahead of the residency scope reddens
  ``test_the_record_reaches_brain_active_only_once_the_deep_model_serves``;
- dropping the conductor's ``except`` that fails the record on teardown reddens ``mid-drain``,
  ``after-drain``, ``after-cortex-stop``, ``mid-brain-stream``, ``after-brain-persist`` and
  ``during-swap-back``; ``after-snapshot`` is reddened by dropping the same guard around the
  record's first write instead, which is a separate mutation and a separate defect (one this
  suite found: a kill there used to strand a live record that refused every later handoff);
- dropping ``undrain`` from the conductor's ``finally`` reddens every case that got as far as
  draining (``after-drain`` onwards) plus
  ``test_a_drain_that_times_out_converges_without_evicting_anything``;
- a drain that reports clean on timeout reddens that same drain-timeout case;
- skipping the stranded-record failure, or the stop of a still-running deep model, in boot
  recovery reddens
  ``test_boot_recovery_fails_a_stranded_record_and_converges_without_double_running``.
"""

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
    """Invariant 4: nothing on the stream claimed more than the machine actually did.

    A handoff that runs to an end always says something: a deep answer, or the note explaining
    why there is none. A **killed** one may not have got a word out, because the kill can land
    before the first status; the ending the caller then sees is the cancellation itself, which
    the seam turns into a terminal error rather than silence (proven end to end over the real
    stream in the orchestrator's ``test_converse_handoff.py``). What must never happen either
    way is an event claiming progress that did not happen.
    """
    for event in events:
        assert isinstance(event, StatusUpdate | TextDelta)
        if isinstance(event, StatusUpdate):
            assert event.state == SWAPPING_STATE
    if not killed:
        assert any(isinstance(event, TextDelta) for event in events)


async def assert_the_next_turn_still_works(live: Harness) -> None:
    """A converged system is one the next turn can use: the cortex leases again, at once.

    Deliberately the lease and not a second handoff: a host scripted to refuse the deep model
    forever would refuse the next handoff too, which says nothing about whether the machine
    recovered. What every case owes is that the cortex is resident, the scope is released, and
    the lease is free, which is exactly what the next user turn needs. The full next-turn path
    over the real stream is proven at the seam (``test_converse_handoff.py``).
    """
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
    """The kill no conductor can clean up after: the process itself died mid-handoff.

    Nothing else could have run, so the state is built as a crash would have left it: a live
    BRAIN_ACTIVE record and the deep model resident. Recovery fails the record and puts the
    cortex back, and deliberately does NOT resume the deep phase, since replaying it without a
    request-identity design risks double-running side-effectful work.
    """
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
