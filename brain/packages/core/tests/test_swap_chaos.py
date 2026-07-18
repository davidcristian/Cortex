"""THE chaos suite: kill the handoff at every step boundary, and prove it always converges.

This is the CI half of ADR-0030 decision 7 and the gate the one hard rule is proven by. The
same real composition the conductor suite drives (real conductor, real residency manager, real
drain, real deep phase, over the scripted host and in-memory stores) is killed at each boundary
of the swap sequence, and every case asserts the same four invariants:

1. **the standing residency is back**: the exit path asked for the cortex back whenever
   anything was evicted, and the host ends running the cortex plus every tier the swap evicts;
2. **the pool admits again, and not one moment earlier**: the drain window is released whatever
   ended the handoff, and every release is witnessed against the residency that was running when
   it happened, because a window reopened halfway through a swap back looks identical afterwards;
3. **the stores are intact**: the user message and the cortex's reply are still there, no
   partial deep answer is persisted as a completed one, the durable memory holds this turn's
   exchange or nothing at all (never a half-written or invented one), no handoff is left live,
   and the record reached a terminal state (which a clean handoff then deletes, so it is the
   write log that proves it);
4. **the stream ended honestly**: every event it emitted was true when it was emitted, which is
   asserted per status against the work that status announces (the swap window's own witness,
   in the harness) and not merely against the order of the other three; and the next turn works.

Three kinds of kill. A **scripted failure** (a host that refuses, a model that never loads, a
server that dies mid-answer, a store that refuses the write which ends the handoff) exercises
the conductor's own error paths. A **cancellation** at
an armed boundary is the process-death analogue on the consumer side: the task running the
handoff is cancelled exactly there, which is what a killed turn does. A **close** is the third
and it is not the same thing: production tears a stream down by closing the generator, not by
cancelling its task, and a cancellation unwinds the inner generators inline, so only a close
can discriminate the conductor's own deterministic teardown.

Determinism: every boundary is an ``asyncio.Event`` pair, every elapsed bound is passed as zero
(already expired), and ``_settle`` yields the loop a few turns. No test sleeps wall-clock.

Order independence is a **separate** claim from that one, and it was measured rather than
assumed. Nothing shuffles tests here: this environment has no test-ordering plugin installed, so
a ``-p no:randomly`` on a command line is inert and citing it establishes nothing. What
establishes it is a real shuffled run, done on 2026-07-18 with the plugin supplied for the run
only (``uv run --with pytest-randomly pytest -p randomly --randomly-seed=N``): three seeds over
``packages/core`` and one over the whole brain workspace, all green, with the collected order
confirmed to differ between seeds so the shuffle was doing something. Repeat that command rather
than a flag that names a plugin nothing installed.

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
  ``test_boot_recovery_fails_a_stranded_record_and_converges_without_double_running``;
- taking the single-handoff precondition as a store read rather than as the residency claim
  reddens ``test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched``, which
  the in-memory store alone cannot do (hence ``_YieldingHandoffStore``);
- dropping the conductor's ``aclose`` on its swap generator reddens
  ``test_closing_the_stream_mid_handoff_unwinds_the_swap_rather_than_abandoning_it``, and
  nothing else here, because every other case cancels;
- each of the swap window's four statuses, moved off the work it announces, reddens through the
  harness's per-status witness. None of the four changes the ORDER the details arrive in, which
  is what the old assertion read and why it caught none of them. Each reddens the cases that got
  far enough to emit the status in question: "draining" moved after the drain reddens every case
  whose drain returned; "loading" moved inside the residency scope reddens every case whose deep
  model actually loaded; "working on this" moved above that scope reddens every case that entered
  the swap at all (it used to redden only the cases that never reached the deep model, which is
  why the witness replaced the old check); "restoring" moved below the scope reddens every case
  whose deep model answered;
- one shielded wait for the restore instead of one per cancellation (which is what the seam
  actually delivers: ``ConverseStream`` cancels the turn from its pump, then again from
  ``events()``'s teardown) reddens
  ``test_a_second_cancellation_during_the_swap_back_still_holds_the_drain_window_shut`` and
  nothing else, that being the only case that cancels twice;
- hoisting the conductor's ``undrain`` above the ``aclose`` that unwinds the swap reddens
  ``test_closing_the_stream_mid_handoff_unwinds_the_swap_rather_than_abandoning_it`` and nothing
  else, for the same reason as the ``aclose`` mutation above: every other case cancels, and a
  cancellation has already unwound the scope by the time the conductor's ``finally`` runs;
- dropping the ``aclose`` on the DEEP MODEL's own round (the innermost of the three teardowns)
  reddens that same close case and nothing else. Only the round's own witness can see it: the
  swap back and the drain window are both intact under this mutation, so every other assertion
  in the suite, including the two the close case made before, passes;
- restarting nothing after the cortex comes back reddens
  ``test_a_tier_evicted_for_the_handoff_is_running_again_when_it_ends``;
- pausing the mid-drain case before the refusal window opens (which is where it used to
  pause, making it a duplicate of ``after-snapshot``) reddens
  ``test_the_mid_drain_kill_lands_while_the_pool_is_actually_quiescing``;
- the pool's own ``drain`` no longer opening the refusal window at all reddens ``mid-drain``
  and that same boundary case, which is the mutation that proves the boundary is REACHED
  rather than staged: while the harness set the draining flag itself, this mutation passed;
- releasing the record's claim only when the settling write landed reddens both cases of
  ``test_a_store_that_refuses_the_settling_write_still_frees_the_next_handoff``.
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
    WitnessingScheduler,
    assert_the_window_announced_real_progress,
    build_harness,
)

from cortex_core import (
    ALREADY_ACTIVE_NOTE,
    BRAIN_FAILED_NOTE,
    SWAP_FAILED_NOTE,
    SWAPPING_STATE,
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

# How far the host has been driven at each boundary, ignoring readiness polls: the eviction, the
# swap in, and the whole way back. Naming them keeps each case's expectation readable.
_EVICTED = (("stop", "cortex"),)
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
    """A pool that pauses the handoff at a drain boundary: inside the window, or once drained.

    ``mid`` is the ADR's mid-drain kill point and it has to land where its name says, so the
    window it pauses inside must be opened by the POOL's own ``drain`` and never by this
    harness. A harness that opened it itself would hold the handoff at a boundary the pool had
    not reached, and every assertion about that boundary would then be satisfied by the harness
    rather than by the code under test, which is the defect this case exists to rule out.

    So the straggler does the waiting. It is admitted before the drain begins, it watches the
    pool's own condition until ``drain`` raises the refusal window around it, and only then
    does it fire the gate, holding the admission the whole time. The handoff is therefore
    suspended inside the real ``drain``, quiescing, with work genuinely in flight, rather than
    at the same system state as ``after-snapshot``. ``after`` pauses once the pool has fully
    drained, the other edge.
    """

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
    """A store whose verbs suspend, as a real network store's do; the in-memory twin never does.

    The single-handoff precondition is a read followed by a write. Over a store that cannot
    suspend between them two concurrent handoffs can never interleave there, so the in-memory
    fake structurally cannot exhibit the race the residency claim exists to close, and a suite
    built only on it would call the defect green. This one can: every verb yields the loop
    first, and the first ``put`` is held at a gate, which is precisely the window a second
    escalating turn would slip through.
    """

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
    """Invariants 1 and 2: the standing residency is back and the pool admits again.

    Standing residency is the cortex AND every tier the swap evicts for the deep model's sake:
    ``undrain`` reopens the pool to spawns the moment a handoff ends, so a subagent tier left
    stopped would take delegated work on a server nothing ever restarted.

    Which is why the window's release is asserted at the moment it happened and not only at the
    end. "The pool admits again" is true of a handoff that reopened admission halfway through
    its own swap back, and by the time anything can be asked afterwards the restore has caught
    up and erased the difference. So every reopening is witnessed against the residency that was
    actually running when it happened.
    """
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
    # The durable store too, which a memory-less capabilities bundle would have made vacuous: a
    # deep phase that finished records exactly its own exchange, and nothing else ever records
    # anything at all. A kill can land between the reply's append and the memory write, so a
    # killed case may be missing it; what neither case may be is half written or invented.
    remembered = [memory.text for memory in await live.remembered()]
    written = [] if deep_reply is None else [render_exchange(harness.USER_TEXT, deep_reply)]
    if killed:
        assert remembered in ([], written)
    else:
        assert remembered == written


def assert_stream_ended_honestly(live: Harness, events: list[TurnEvent], *, killed: bool) -> None:
    """Invariant 4: no event claimed progress the machine had not actually made.

    Each status is checked against the work it announces, not merely against the other statuses
    (``assert_the_window_announced_real_progress`` holds that contract and says why an order
    among the four strings constrains almost nothing on its own). What is left here is the
    shape of the stream itself: nothing but swap-window statuses and reply text crosses it, and
    every status rides the one state the overlay renders as a chip.

    A handoff that ran to an end always says something too: a deep answer, or the note that
    explains why there is none. A **killed** one may not have got a word out, because the kill
    can land before the first status; what it still owes is that whatever DID reach the stream
    was true. What a cancelled case deliberately does NOT prove is how the RPC then ends for
    the client: that is the seam's contract, it is tested at the seam, and it is not observable
    from here, where the cancellation simply propagates to the caller.
    """
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
    assert live.host.calls == []  # the whole point: nothing was evicted
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live)
    assert_stream_ended_honestly(live, events, killed=False)
    # The fourth invariant this case owed and did not check: the lease is free again while the
    # straggler that aborted the handoff is STILL running, so the next turn is not held behind
    # a swap that never happened.
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
    """The kill point the suite had at no boundary at all: the store, on the write that ends it.

    Nothing is drained or evicted differently here, so the state that matters is the store's
    own active pointer: the ``READY`` write claims it and the settling write releases it. One
    transient refusal of that settling write therefore used to leave a FINISHED handoff holding
    the pointer, after which ``active()`` refused every later escalation in this process with a
    note saying a handoff was in flight when none was, until a restart. Both settles are
    covered, the clean one and the aborted one, because they release the pointer by different
    means (a delete after ``DONE``, the terminal write itself for ``FAILED``).

    The last block is the assertion that catches the wedge, and it is why one case is not
    enough: converging this turn says nothing about whether the NEXT one can still escalate.
    """
    del case  # named for the parametrize id
    live = make()
    await live.seed_session()
    events = await harness.run_handoff(live, harness.armed_slot())
    await assert_converged_on_cortex(live)
    await assert_stores_intact(live, deep_reply=deep_reply, settled=False)
    assert_stream_ended_honestly(live, events, killed=False)
    await assert_the_next_turn_still_works(live)

    later = await harness.run_handoff(live, harness.armed_slot(), turn_id=_LATER_TURN)
    # It ran: it answered, or it failed at the swap the way this harness's host makes every
    # handoff fail. What it must NOT say is that another handoff is already running.
    assert _texts(later) == later_text
    assert ALREADY_ACTIVE_NOTE not in _texts(later)
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
    assert_stream_ended_honestly(live, events, killed=True)
    await assert_the_next_turn_still_works(live)


async def test_the_mid_drain_kill_lands_while_the_pool_is_actually_quiescing() -> None:
    """The mid-drain boundary is a different system state from after-snapshot, and this pins it.

    Without this the case degrades silently into a second kill-before-anything-happened, which
    is what it used to be: the ADR's point is a kill while the pool is QUIESCING, so its
    boundary owes admission already refused, an admitted request still in flight, and nothing
    evicted. All three are asserted here, at the same gate the parameterized case cancels at.
    """
    gate = Gate()
    scheduler = _PausingScheduler(mid=gate)
    live = build_harness(scheduler=scheduler)
    await live.seed_session()
    events: list[TurnEvent] = []
    task = asyncio.create_task(_consume(live, events))
    await gate.arrived()
    assert scheduler.draining is True  # the refusal window is open
    with pytest.raises(SubagentAdmissionError):
        await _admit(live)
    assert scheduler.straggler is not None
    assert not scheduler.straggler.done()  # and work really is still in flight
    assert live.host.calls == []  # while nothing at all has been evicted
    task.cancel()
    gate.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await _settle()
    await assert_converged_on_cortex(live)


async def test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched() -> None:
    """One GPU means one handoff, and the loser must not have run the prologue at all.

    The precondition cannot be a store read acted on two awaits later. Over a store whose
    verbs suspend (Redis's do), both escalating turns see no active handoff, both write a
    record, and the loser then drains the pool and reopens it in its own ``finally`` while the
    winner's deep model is resident, contradicting both "while draining and for the whole
    handoff, admit refuses" and "while the brain is resident it is alone on the GPU". So the
    claim is taken first, and the loser is told the one thing that is true: a handoff is
    already running, and nothing was unloaded for this one.

    One conductor drives both turns because a conductor holds no per-handoff state; what two
    streams genuinely share is the manager and the stores, and those are shared here.
    """
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
    """A consumer that walks away is not a cancellation, and it must converge just the same.

    This is the production teardown shape: ``converse`` closes the engine's stream when the
    client goes away, which closes this generator rather than cancelling the task running it.
    Every other case here cancels, and a cancellation unwinds the inner generators inline, so
    nothing else in the suite can tell a conductor that closes its swap deterministically from
    one that leaves the deep model resident and the cortex evicted until the collector runs.

    It is closed with the deep model mid-answer, which is the only place all three teardowns
    the conductor owes are outstanding at once: the deep model's own round, the residency
    scope, and the drain window. Each is asserted on its own witness below, because the swap
    back alone would pass while a round was left suspended for the collector to finalize.
    """
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
    """Two cancellations, which is what the seam actually delivers, must not free the pool early.

    ``ConverseStream`` cancels the in-flight turn from its pump when the client asks to stop,
    and again from ``events()``'s own teardown when the stream then goes away; both land on the
    same task, and a swap back takes minutes, so the second one arrives while the first is still
    unwinding the restore. The restore is shielded precisely so a cancellation waits for it, but
    ONE shielded wait is abandoned by the next delivery, and the conductor reopens subagent
    admission the moment the scope returns. That is the harm: the window lifts onto a cortex
    that is still stopped and a tier nothing has restarted, and every other assertion in this
    suite is made after the abandoned restore has quietly finished in the background.

    The evicted tier is what makes it visible: it is restarted last, so it is the last thing a
    prematurely reopened window can be pointed at.
    """
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
    """Convergence means the standing residency, not the cortex alone.

    The pool starts admitting again the instant the handoff ends, so a GPU-placed subagent
    tier that the swap stopped and nothing restarted would be handed delegated work on a dead
    server. The exit that restores the cortex restores it too.
    """
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
    """The other half of the hard rule, inside the artifact that claims to prove it end to end.

    Taint that did not survive would fail open on the far side of the swap: the deep model
    holds the same tools and the same outbound surface, and the laundering evidence is what
    stops it completing an exfiltration the cortex was already refused.
    """
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
    assert live.host.calls == []  # queued behind the round, not preempting it
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
