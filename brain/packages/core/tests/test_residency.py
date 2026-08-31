"""SwappingModelManager: the unchanged lease, plus the one scope that changes residency.

The two halves are tested against each other on purpose, because their interaction is the whole
design: the swap happens only at a lease-free boundary, a queued acquire of another model waits
instead of failing, and the cortex restore lives in the scope's ``finally`` so it runs on
success, on a failed swap-in, on an exception, and under cancellation alike.

Every wait here is event-driven: leases are held open on ``asyncio.Event``s, readiness bounds
that must elapse are passed as ``load_timeout_s=0.0`` (already expired), and ``_settle`` yields
the loop a few turns, which is scheduling, not time. No test sleeps wall-clock.

Mutations proving these tests can fail (each was applied on its own, then restored):
- removing the ``finally`` around ``_restore`` (restoring only on the happy path) fails
  ``test_a_failed_swap_in_still_restores_the_cortex``,
  ``test_an_exception_inside_the_scope_still_restores_the_cortex`` and
  ``test_cancelling_the_scope_still_restores_the_cortex``;
- swapping in without taking the lease first fails
  ``test_the_swap_waits_for_the_in_flight_round_to_fall_free``, and taking the lease for the
  stops but not for the restore fails
  ``test_the_restore_waits_for_the_new_resident_s_own_round``;
- awaiting the restore directly instead of shielding it (so a cancellation abandons it midway)
  fails ``test_a_cancelled_scope_cannot_abandon_the_restore_halfway``;
- making ``ResidencyBoard.await_resident`` raise for a non-scope model instead of waiting fails
  ``test_an_acquire_of_another_model_waits_out_the_scope_instead_of_failing``;
- dropping ``ResidencyBoard.leave_scope``'s ``notify_all`` leaves a queued acquire asleep whenever
  the restore did not itself publish a residency change, which fails
  ``test_a_queued_acquire_is_woken_even_when_the_swap_back_failed`` by timeout (the
  happy-path test alone does NOT discriminate it, which is why that second test exists);
  re-measured on 2026-08-09 after the bookkeeping moved into ``residency_board.py``, it fails 3,
  that case plus the two other waits that then never wake;
- reading the claim and setting it two statements apart (an await between them) fails the
  chaos suite's ``test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched``, and
  dropping the refusal outright (``residency_claim.py``, where the rule now lives) fails that
  case plus ``test_the_handoff_claim_refuses_a_second_holder_without_touching_the_host``;
- restarting nothing after the cortex comes back fails
  ``test_the_scope_swaps_in_evicts_everything_else_and_restores_all_of_it``.

Three more for the residency report the seam publishes, each applied to production code alone
with the whole brain workspace re-run, so the counts are what actually failed:

- answering from the board's resident instead of the report the swap publishes (the wrong source: it
  cannot tell a swap in from a swap back) fails 5, the three report cases here plus
  ``test_health_reports_the_swap_window_it_is_in`` and
  ``test_health_tells_the_truth_about_residency_through_the_whole_wiring`` in the orchestrator.
  It does **not** discriminate the two stalled-load cases, because nothing is resident there
  either, which is why the restore and give-up cases exist beside them;
- dropping the give-up report (so a manager that stopped trying still says it is restoring)
  fails exactly 1, ``test_a_restore_that_gave_up_stops_claiming_it_is_still_restoring``;
- publishing not-ready as soon as a handoff is claimed fails exactly 1,
  ``test_a_claimed_handoff_still_reports_serving_because_the_cortex_still_serves``.

Four more, added because the three above pin only *which* value was published and nothing about
what it says: an audit measured that flipping ``RESIDENCY_RESTORING.serving`` or
``RESIDENCY_LOST.serving`` to ``True``, or blanking every not-serving ``detail``, left the whole
workspace passing. Each below was applied to production code alone and the workspace re-run:

- ``serving=True`` on ``RESIDENCY_RESTORING`` fails 2,
  ``test_every_published_report_says_what_the_seam_and_the_human_actually_read`` plus the seam's
  ``test_health_stays_not_ready_through_the_swap_back``; the same edit to ``RESIDENCY_LOST``
  fails that first case plus ``test_health_stays_not_ready_after_a_restore_that_gave_up``, and
  to ``RESIDENCY_BOOT_FAILED`` that first case plus the composition root's boot case;
- blanking all five not-serving details fails exactly 1, that same first case, which is also
  what keeps the four swap windows from collapsing into one indistinguishable report;
- dropping the not-serving branch of ``publish_boot_residency`` fails 2,
  ``test_boot_recovery_s_observation_replaces_the_seed_a_fresh_manager_started_with`` and the
  composition root's boot case;
- clearing the resident in that publish (treating an unconfirmed boot as a known-dead GPU)
  fails exactly 1, ``test_a_boot_that_could_not_confirm_the_cortex_still_leases_a_working_one``.

One more for who says a thing, rather than what is said. ``caplog``'s handler sits on the root
logger, so a ``logger=`` argument to ``at_level`` decides only whether a record is enabled, never
which records are collected: at WARNING and above the root level enables them all, and naming a
module there pins nothing. Measured, with the emission of "the model host failed while restoring
the cortex" moved to a logger of another name: under a ``logger=`` filter naming its real module
the restore case still passed, and only once the assertions carried ``record.name`` did the same
move fail both restore cases below. So the two of them assert the emitting module, and the
filter names it for the reader.

Two more for the daemon a handoff is about to spend its beliefs against, measured the same way
(``residency_watch.py`` holds the rest of that suite). Dropping the reconcile from ``_swap_in``
fails 9: the three cases here that watch a restart or read the op log, plus
``test_swap_conductor.py``'s clean handoff and four chaos boundaries, all of which pin the ask as
the first thing a swap does to the host. Dropping the seed from ``publish_boot_residency`` fails
2, both restart cases here, since a comparison with nothing on the other side of it never fires.

Three more for the model a restore failure names, measured once the eviction and the start stopped
sharing a ``try``, each applied to production code alone with the whole brain workspace re-run:

- naming the cortex on the eviction's failure fails **1**,
  ``test_a_restore_that_cannot_evict_the_deep_model_names_it_and_not_the_cortex``;
- naming the swapped-in model on the cortex's own failure fails **1**,
  ``test_a_restore_that_fails_once_retries_and_succeeds``, which is what the fields added to that
  case's assertions buy: on the message alone it still passed;
- putting the eviction, the start and the gate back under one ``try`` fails **1**, the eviction
  case, which is the only one whose failure the collapsed arm would name wrongly.

Six more for carrying that model out of the attempt rather than a bool, measured the same way
(each applied to production code alone, the whole brain workspace re-run at 2753 tests):

- the eviction answering the cortex fails **2**, the eviction retry case and the give-up that
  never evicts;
- the cortex's own start answering the swapped-in model fails **2**, the retry case and the
  give-up that never starts;
- a stalled gate answering the swapped-in model fails **1**,
  ``test_a_restore_whose_gate_never_reports_ready_also_gives_up``, which is the one path where
  nothing refused anything and the model still did not come up;
- the retry line's ``failed_model`` pinned to the cortex fails **1**, the eviction retry case,
  which is the only one where the two models differ and therefore the only one that can catch it;
- the give-up line dropping ``failed_model`` fails **2**, both give-up cases;
- the give-up message dropping the tier it failed on fails **3**, all three give-ups, which is
  the sentence an operator carries to the runbook.
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    RESIDENCY_BOOT_FAILED,
    RESIDENCY_DEEP,
    RESIDENCY_LOADING,
    RESIDENCY_LOST,
    RESIDENCY_RESTORING,
    RESIDENCY_SERVING,
    ControlBounds,
    DeviceMemory,
    HandoffInProgressError,
    ModelHost,
    ModelHostState,
    ModelManager,
    ModelUnavailableError,
    RecordingSleeper,
    ResidencyController,
    ResidencyPlan,
    ResidencyReport,
    ResidencyReporter,
    ResidencyRestoreError,
    ScriptedModelHost,
    SwapFailedError,
    SwappingModelManager,
    record_fields,
)

_CORTEX_URL = "http://llama-cortex:8080"
_BRAIN_URL = "http://llama-brain:8081"
_ENDPOINTS = {"cortex": _CORTEX_URL, "brain": _BRAIN_URL}


class _FixedClock:
    """A clock that never advances: an elapsed bound is one that was already expired."""

    def now(self) -> datetime:
        return datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


class _YieldingHost:
    """A host whose every operation suspends, as a real supervisor's HTTP calls do.

    The scripted twin answers without ever yielding, which hides one interleaving: a waiter
    woken mid-restore re-checks while the scope is still active and goes back to sleep, so only
    the scope's own end can wake it again. This wrapper is what exposes that.
    """

    def __init__(self, inner: ScriptedModelHost) -> None:
        self._inner = inner

    async def start(self, model: str) -> None:
        await asyncio.sleep(0)
        await self._inner.start(model)

    async def stop(self, model: str) -> None:
        await asyncio.sleep(0)
        await self._inner.stop(model)

    async def status(self, model: str) -> ModelHostState:
        await asyncio.sleep(0)
        return await self._inner.status(model)

    async def device_memory(self) -> DeviceMemory | None:
        await asyncio.sleep(0)
        return await self._inner.device_memory()

    async def control_bounds(self) -> ControlBounds | None:
        await asyncio.sleep(0)
        return await self._inner.control_bounds()

    async def boot_id(self) -> str | None:
        await asyncio.sleep(0)
        return await self._inner.boot_id()


def _manager(host: ModelHost, plan: ResidencyPlan | None = None) -> SwappingModelManager:
    return SwappingModelManager(
        host, _ENDPOINTS, plan if plan is not None else _plan(), _FixedClock(), RecordingSleeper()
    )


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few turns so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


async def _lease(manager: SwappingModelManager, model: str) -> str:
    async with manager.acquire(model) as lease:
        return lease.endpoint


class _HeldLease:
    """One in-flight inference round, holding the GPU lease until told to finish."""

    def __init__(self, manager: SwappingModelManager, model: str) -> None:
        self._manager = manager
        self._model = model
        self.holding = asyncio.Event()
        self.release = asyncio.Event()
        self.task: asyncio.Task[None] = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async with self._manager.acquire(self._model):
            self.holding.set()
            await self.release.wait()

    async def started(self) -> None:
        async with asyncio.timeout(5.0):
            await self.holding.wait()

    async def finish(self) -> None:
        self.release.set()
        await self.task


class _OpenScope:
    """A residency scope held open until told to leave, so the test drives both boundaries."""

    def __init__(self, manager: SwappingModelManager, model: str = "brain") -> None:
        self._manager = manager
        self._model = model
        self.entered = asyncio.Event()
        self.leave = asyncio.Event()
        self.task: asyncio.Task[None] = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async with self._manager.swap_scope(self._model):
            self.entered.set()
            await self.leave.wait()

    async def start(self) -> None:
        async with asyncio.timeout(5.0):
            await self.entered.wait()

    async def finish(self) -> None:
        self.leave.set()
        await self.task


async def test_acquire_leases_the_resident_model_unchanged() -> None:
    """v1's contract survives the swap: the resident leases, anything else is unavailable."""
    manager: ModelManager = _manager(ScriptedModelHost(running=["cortex"]))
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL
    with pytest.raises(ModelUnavailableError, match="'brain' is not resident"):
        async with manager.acquire("brain"):
            pass  # pragma: no cover - acquire raises before the body runs
    with pytest.raises(ModelUnavailableError, match="no configured endpoint"):
        async with manager.acquire("nonesuch"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_acquire_serializes_callers_on_the_one_gpu() -> None:
    """The lease is still a single lock: a second caller waits for the first to leave."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    held = _HeldLease(manager, "cortex")
    await held.started()
    second = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not second.done()
    await held.finish()
    assert await second == _CORTEX_URL


async def test_the_scope_swaps_in_evicts_everything_else_and_restores_all_of_it() -> None:
    """Decision 4 step 3's ordering, read straight off the host's op log.

    The exit's job is the STANDING residency, not the cortex alone: the evicted subagent tier
    is put back too, after the cortex is gated, or the conductor would reopen admission to a
    tier the swap killed and nothing would ever restart.
    """
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    manager = _manager(host, _plan(evict_models=("subagent-gpu",)))
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}  # while the brain is resident it is alone on the GPU
        async with manager.acquire("brain") as lease:
            assert lease.endpoint == _BRAIN_URL
    assert host.calls == [
        ("boot_id", ""),
        ("stop", "cortex"),
        ("stop", "subagent-gpu"),
        ("start", "brain"),
        ("status", "brain"),
        ("stop", "brain"),
        ("start", "cortex"),
        ("status", "cortex"),
        ("start", "subagent-gpu"),
    ]
    assert host.running == {"cortex", "subagent-gpu"}
    async with manager.acquire("cortex") as lease:  # the cortex serves again, unchanged
        assert lease.endpoint == _CORTEX_URL


async def test_a_tier_that_will_not_restart_does_not_make_the_cortex_look_gone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The evicted tier's restart is best effort, because a failed-restore note would be
    inaccurate here.

    Telling the user "the usual assistant could not be reloaded" when the cortex is serving and
    only the delegation tier is down would be the opposite of honest, so the failure is loud in
    the log and invisible to the turn.
    """
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"], fail={("start", "subagent-gpu"): "no such device"}
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",)))
    with caplog.at_level(logging.ERROR, logger="cortex_core.residency_moves"):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert [record.message for record in caplog.records] == [
        "a tier evicted for the handoff could not be restarted"
    ]
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_the_swap_waits_for_the_in_flight_round_to_fall_free() -> None:
    """v1 never preempts a mid-stream round: nothing is evicted while a lease is held."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    held = _HeldLease(manager, "cortex")
    await held.started()
    scope = _OpenScope(manager)
    await _settle()
    assert host.calls == []  # the swap is queued behind the round, not preempting it
    await held.finish()
    await scope.start()
    assert ("stop", "cortex") in host.calls
    await scope.finish()


async def test_an_acquire_of_another_model_waits_out_the_scope_instead_of_failing() -> None:
    """A queued cortex turn on a second stream blocks until restoration, then runs."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    scope = _OpenScope(manager)
    await scope.start()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()  # waiting, not raising ModelUnavailableError
    await scope.finish()
    async with asyncio.timeout(5.0):
        assert await waiting == _CORTEX_URL


async def test_a_queued_acquire_is_woken_even_when_the_swap_back_failed() -> None:
    """The queue is released by the scope ENDING, not by the restore succeeding.

    Otherwise the one failure the design cannot recover from would also strand every waiter: a
    turn on another stream would sleep forever instead of hearing that nothing is resident.
    """
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(_YieldingHost(host))
    scope = _OpenScope(manager)
    await scope.start()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()
    scope.leave.set()
    with pytest.raises(ResidencyRestoreError):
        await scope.task
    async with asyncio.timeout(5.0):
        with pytest.raises(ModelUnavailableError, match="resident: None"):
            await waiting


async def test_the_restore_waits_for_the_new_resident_s_own_round() -> None:
    """The swap back is a lease-free boundary too: a brain round in flight is not preempted."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    held = _HeldLease(manager, "brain")
    await held.started()
    scope.leave.set()
    await _settle()
    assert not scope.task.done()  # the restore is queued behind the brain's round
    assert ("stop", "brain") not in host.calls
    await held.finish()
    await scope.task
    assert host.running == {"cortex"}


async def test_a_second_scope_is_refused_because_there_is_one_gpu() -> None:
    """A second scope is refused as a handoff already in flight rather than as a swap that broke.

    The distinction is what the user is told: a broken swap means nothing is loaded and the
    cortex is back, which is the opposite of what is true while another handoff holds the GPU.
    """
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    scope = _OpenScope(manager)
    await scope.start()
    with pytest.raises(HandoffInProgressError, match="already active"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    await scope.finish()


async def test_the_precondition_reads_the_roster_of_the_daemon_answering_right_now() -> None:
    """The port's three answers, and the tolerance that makes only one of them a refusal.

    A tier the host says it does not carry is the deployment fact the conductor rejects. A
    tier it does carry is not, and neither is a host that could not be asked: over-refusing there
    would turn one unreachable moment into "this deployment cannot escalate". Nothing is
    remembered between the three, which is the property the whole design rests on, so the same
    manager answers differently the moment the roster it is asking about does.
    """
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    manager = _manager(host)
    assert await manager.unhosted("brain") is True
    host.unhosted.discard("brain")  # an operator named the artifact and the daemon came back
    assert await manager.unhosted("brain") is False
    # A reading and nothing more: the question must never change what the card is holding.
    assert host.calls == [("status", "brain")] * 2
    assert host.running == {"cortex"}
    unreachable = ScriptedModelHost(running=["cortex"], fail={("status", "brain"): "refused"})
    assert await _manager(unreachable).unhosted("brain") is False


async def test_the_handoff_claim_refuses_a_second_holder_without_touching_the_host() -> None:
    """The claim is taken before anything is drained, so losing it costs nothing at all."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    async with manager.handoff_claim():
        with pytest.raises(HandoffInProgressError, match="one GPU"):
            async with manager.handoff_claim():
                pass  # pragma: no cover - entering raises before the body runs
        # The cortex is untouched and still leasable: a refused claim is not a swap window.
        assert host.calls == []
        async with manager.acquire("cortex") as lease:
            assert lease.endpoint == _CORTEX_URL
    # And the claim is released on the way out, so the next handoff can take it.
    async with manager.handoff_claim():
        pass


async def test_a_claim_is_released_even_when_its_holder_is_cancelled() -> None:
    """A killed turn must not leave the machine unable to escalate ever again."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    holding = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with manager.handoff_claim():
            holding.set()
            await release.wait()

    task = asyncio.create_task(hold())
    async with asyncio.timeout(5.0):
        await holding.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with manager.handoff_claim():
        pass


async def test_a_failed_swap_in_still_restores_the_cortex() -> None:
    """The brain will not start: the scope's finally puts the cortex back before raising."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", "brain"): "CUDA OOM at load"})
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="CUDA OOM at load"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}
    assert ("start", "cortex") in host.calls
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_swap_into_a_tier_the_host_never_had_says_so_rather_than_blaming_the_host() -> None:
    """A handoff asking for an unrostered tier is a configuration fault, and the note says which.

    The same 404 boot recovery now tolerates for the deep tier is fatal here, and rightly: an
    escalation that cannot happen has to fail. What changes is the sentence the user's turn is
    told, because "the model host failed" invites a retry that will fail identically every time,
    for as long as that daemon runs.

    The last assertion is the graver half. The swap back stops the model it swapped in, and that
    stop meets the very same 404; read as a machine failure it fails the restore, and both
    attempts fail it, so a deployment that merely could not escalate would end with the cortex
    evicted, ``ResidencyRestoreError`` raised, and the seam saying the GPU serves nothing.
    """
    host = ScriptedModelHost(running=["cortex"], unhosted=["brain"])
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="does not serve 'brain' at all"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "cortex") in host.calls
    assert host.running == {"cortex"}
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_brain_that_never_becomes_ready_fails_the_swap_at_the_gate() -> None:
    """The health gate's bound is the swap's, so a stuck load aborts instead of hanging."""
    host = ScriptedModelHost(running=["cortex"], status_override={"brain": ModelHostState.LOADING})
    manager = _manager(host, _plan(load_timeout_s=0.0))
    with pytest.raises(SwapFailedError, match="did not become ready in time"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}


async def test_a_brain_that_dies_at_load_fails_the_swap_with_its_state() -> None:
    host = ScriptedModelHost(running=["cortex"], status_override={"brain": ModelHostState.FAILED})
    manager = _manager(host)
    with pytest.raises(SwapFailedError, match="last state: failed"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert host.running == {"cortex"}


async def test_a_swap_is_refused_when_the_card_has_no_room_for_the_deep_model() -> None:
    """The fit check, on the numbers measured 2026-08-07: 13165 MiB free against 19125 wanted.

    What the deep model would otherwise do is start anyway and be paged to system memory, which
    is why the assertion is on ``calls``: no ``start`` for the deep model at all. A refusal that
    merely raised after loading would be worse than none.
    """
    host = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=13165, total_mib=24463)
    )
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with pytest.raises(SwapFailedError, match="needs 19125 MiB of free device memory"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_the_card_is_read_after_the_evictions_and_before_the_load() -> None:
    """The one instant the reading means anything, asserted as its place in the op log.

    Read earlier and the check would charge the deep model for tiers this handoff is about to
    unload, refusing swaps that fit; read later and it would be reading a card the load has
    already overcommitted, which measures the same either way (a fit and a 4676 MiB spill both
    left about 0.5 GB free). So its position between the last stop and the start is the
    behaviour, not an implementation detail.
    """
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"],
        device_memory=DeviceMemory(free_mib=20033, total_mib=24463),
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), brain_vram_mib=19125))
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}
    assert host.calls[:5] == [
        ("boot_id", ""),
        ("stop", "cortex"),
        ("stop", "subagent-gpu"),
        ("device_memory", ""),
        ("start", "brain"),
    ]


async def test_a_card_with_exactly_the_room_is_a_fit_and_one_mib_short_is_not() -> None:
    """The boundary itself, because either side of it is a different deployment's answer."""
    exact = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=19125, total_mib=24463)
    )
    async with _manager(exact, _plan(brain_vram_mib=19125)).swap_scope("brain"):
        assert exact.running == {"brain"}
    short = ScriptedModelHost(
        running=["cortex"], device_memory=DeviceMemory(free_mib=19124, total_mib=24463)
    )
    with pytest.raises(SwapFailedError, match="only 19124 of 24463 MiB is free"):
        async with _manager(short, _plan(brain_vram_mib=19125)).swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs


async def test_a_host_that_can_see_no_card_refuses_a_swap_that_asked_for_a_fit() -> None:
    """The swap fails closed: a deployment that asked to be checked and cannot be is refused
    rather than run."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with pytest.raises(SwapFailedError, match="reports no device memory"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}


async def test_a_plan_with_no_measured_figure_never_asks_the_host_about_the_card() -> None:
    """The shipped default: no figure, no question, and the swap runs exactly as it always did."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    async with manager.swap_scope("brain"):
        assert host.running == {"brain"}
    assert ("device_memory", "") not in host.calls


async def test_a_host_that_fails_the_reading_fails_the_swap_rather_than_skipping_it() -> None:
    """A control call that broke is not permission to load: it is the swap's own failure."""
    host = ScriptedModelHost(
        running=["cortex"], fail={("device_memory", ""): "the model host did not answer"}
    )
    manager = _manager(host, _plan(brain_vram_mib=19125))
    with pytest.raises(SwapFailedError, match="the model host did not answer"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("start", "brain") not in host.calls
    assert host.running == {"cortex"}


async def _blow_up_inside(manager: SwappingModelManager) -> None:
    async with manager.swap_scope("brain"):
        msg = "the brain phase blew up"
        raise RuntimeError(msg)


async def test_an_exception_inside_the_scope_still_restores_the_cortex() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    with pytest.raises(RuntimeError, match="the brain phase blew up"):
        await _blow_up_inside(manager)
    assert host.running == {"cortex"}


async def test_cancelling_the_scope_still_restores_the_cortex() -> None:
    """The process-death analogue on the consumer side: teardown still converges."""
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await scope.task
    assert host.running == {"cortex"}
    assert ("start", "cortex") in host.calls


async def test_a_cancelled_scope_cannot_abandon_the_restore_halfway() -> None:
    """The swap back is the recovery path, so a cancellation waits for it instead of aborting.

    Killing the turn while the cortex is coming back would otherwise leave the GPU serving
    nothing this process can lease again, and every later turn would fail until a restart.
    """
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "cortex")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.leave.set()
    async with asyncio.timeout(5.0):
        await host.reached[("start", "cortex")].wait()
    scope.task.cancel()
    host.release[("start", "cortex")].set()
    with pytest.raises(asyncio.CancelledError):
        await scope.task
    assert host.running == {"cortex"}
    # And the manager knows it: the next turn leases the cortex rather than being told that
    # nothing is resident.
    async with asyncio.timeout(5.0):
        assert await _lease(manager, "cortex") == _CORTEX_URL


async def test_a_restore_that_fails_once_retries_and_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Decision 4 step 3's retry: the second attempt brings the cortex back, loudly noted."""
    host = ScriptedModelHost(running=["cortex"], fail_once={("start", "cortex"): "device busy"})
    manager = _manager(host)
    with caplog.at_level(logging.WARNING):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert host.calls.count(("start", "cortex")) == 2  # the failed attempt, then the retry
    # Each record is pinned to the module that emits it, not only to its text: the attempt is
    # reported where the attempt is made and the retry where the retries are counted, so a
    # message that drifts to another module stops satisfying this test.
    # The fields ride along, because the message alone no longer says which model the host
    # refused: this failure is the cortex's start, and a line naming the other one would send an
    # operator after a tier that is already off the card. ``failed_model`` is the retry line's
    # half of that, and here it agrees with the line above it because the cortex really is what
    # refused; the eviction case below is where the two would part.
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        (
            "cortex_core.residency_moves",
            "the model host failed while restoring the cortex",
            {"model": "cortex"},
        ),
        (
            "cortex_core.residency_restore",
            "restoring the cortex failed; retrying",
            {"model": "cortex", "failed_model": "cortex", "attempt": 1},
        ),
    ]


async def test_a_restore_that_cannot_evict_the_deep_model_names_it_and_not_the_cortex(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The other model a restore can fail about, and the reason its ``try`` is its own.

    The swap back has two subjects: the model it is taking off the card and the cortex it is
    putting back. This failure is the first of them, one call before the cortex is asked about at
    all, so the line names the deep model. The retry then succeeds, which is what makes this the
    ordinary case rather than an outage: a stop that loses one race must not be reported as the
    usual assistant having failed to come back.

    The retry line one module up is the case for carrying the id out of the attempt at all: it is
    about restoring the cortex, which is what ``model`` says, and the tier that actually refused
    is the deep model, which is what ``failed_model`` says. While the attempt answered a bool,
    that second half could only ever be the cortex, so the pair asserted here is the whole
    difference.
    """
    host = ScriptedModelHost(running=["cortex"], fail_once={("stop", "brain"): "still reaping"})
    manager = _manager(host)
    with caplog.at_level(logging.WARNING):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert host.calls.count(("stop", "brain")) == 2  # the refused eviction, then the retry
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        (
            "cortex_core.residency_moves",
            "the model host failed while taking the swapped-in model off the card",
            {"model": "brain"},
        ),
        (
            "cortex_core.residency_restore",
            "restoring the cortex failed; retrying",
            {"model": "cortex", "failed_model": "brain", "attempt": 1},
        ),
    ]


async def test_a_restore_that_never_succeeds_raises_loudly_and_leaves_nothing_resident(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Past the retry only the runbook helps, so the failure is typed, logged, and honest."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(host)
    with (
        caplog.at_level(logging.WARNING, logger="cortex_core.residency_restore"),
        pytest.raises(
            ResidencyRestoreError, match=r"the last of which failed on 'cortex'; manual recovery"
        ),
    ):
        async with manager.swap_scope("brain"):
            pass
    assert host.calls.count(("start", "cortex")) == 2
    # The give-up is the module's own verdict, so the record that carries it has to come from
    # the module that decides it; an error from any other one is a different event. It carries
    # the tier the last attempt failed on beside the cortex it could not restore, which are one
    # model here and two in the case below.
    assert [
        record_fields(record)
        for record in caplog.records
        if record.levelno == logging.ERROR and record.name == "cortex_core.residency_restore"
    ] == [{"model": "cortex", "failed_model": "cortex", "attempts": 2}]
    # Nothing is resident, so an acquire says so rather than leasing a dead endpoint.
    with pytest.raises(ModelUnavailableError, match="resident: None"):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_a_restore_that_can_never_evict_gives_up_naming_the_model_that_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The give-up an operator carries to the runbook, on a restore that failed somewhere else.

    Both attempts fail at the stop of the model the handoff swapped in, so the cortex is never
    asked for at all and the deep model is still the one holding the card. "Could not restore
    the cortex" is true and, on its own, sends a reader after a tier nothing has touched: the
    ``start`` this failure is blamed on never ran. The sentence therefore names what the last
    attempt failed on, in the field and in the exception's own text, which is the whole of what
    a verdict richer than a bool buys one level up.
    """
    host = ScriptedModelHost(running=["cortex"], fail={("stop", "brain"): "still reaping"})
    manager = _manager(host)
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(
            ResidencyRestoreError, match=r"the last of which failed on 'brain'; manual recovery"
        ),
    ):
        async with manager.swap_scope("brain"):
            pass
    assert ("start", "cortex") not in host.calls  # the cortex was never asked for at all
    assert host.running == {"brain"}  # and the deep model is what is really on the card
    refused = (
        "cortex_core.residency_moves",
        "the model host failed while taking the swapped-in model off the card",
        {"model": "brain"},
    )
    assert [(record.name, record.message, record_fields(record)) for record in caplog.records] == [
        refused,
        refused,
        (
            "cortex_core.residency_restore",
            "could not restore the cortex after a model swap; the GPU serves nothing",
            {"model": "cortex", "failed_model": "brain", "attempts": 2},
        ),
    ]
    assert manager.residency() == RESIDENCY_LOST


async def test_a_restore_whose_gate_never_reports_ready_also_gives_up() -> None:
    """The restore's failure is not only a raising host: a cortex stuck loading counts too.

    And it is the cortex the give-up names, on the one path where nothing refused anything: the
    host took every call and the model simply never came up, which is still the model the attempt
    failed on.
    """
    host = ScriptedModelHost(running=["cortex"], status_override={"cortex": ModelHostState.LOADING})
    manager = _manager(host, _plan(load_timeout_s=0.0))
    with pytest.raises(ResidencyRestoreError, match=r"the last of which failed on 'cortex'"):
        async with manager.swap_scope("brain"):
            pass
    assert host.calls.count(("start", "cortex")) == 2


async def test_the_report_tracks_the_swap_window_from_load_to_deep_work_and_back() -> None:
    """What ``Health`` shows a human, read at each boundary the swap actually crosses.

    The load is observed from inside the host's own paused ``start``, so the reported state is
    the one the manager published on its way there rather than one this test arranged.
    """
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "brain")])
    manager = _manager(host)
    assert manager.residency() == RESIDENCY_SERVING
    scope = _OpenScope(manager)
    async with asyncio.timeout(5.0):
        await host.reached[("start", "brain")].wait()
    assert manager.residency() == RESIDENCY_LOADING
    host.release[("start", "brain")].set()
    await scope.start()
    assert manager.residency() == RESIDENCY_DEEP
    await scope.finish()
    assert manager.residency() == RESIDENCY_SERVING


async def test_the_report_says_the_usual_assistant_is_coming_back_while_it_restores() -> None:
    """The swap back publishes a report of its own: nothing is resident either way, and the two
    reports read differently."""
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "cortex")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    await scope.start()
    scope.leave.set()
    async with asyncio.timeout(5.0):
        await host.reached[("start", "cortex")].wait()
    assert manager.residency() == RESIDENCY_RESTORING
    host.release[("start", "cortex")].set()
    await scope.task
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_restore_that_gave_up_stops_claiming_it_is_still_restoring() -> None:
    """A restore that gave up reports that nothing is resident and no retry is left.

    Reporting the restore as still under way would tell the user to wait for a thing that
    already stopped happening, and the runbook's manual recovery is what clears it.
    """
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(host)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope("brain"):
            pass
    assert manager.residency() == RESIDENCY_LOST


async def test_the_report_answers_at_an_instant_when_the_gpu_cannot_be_leased() -> None:
    """A probe must not queue behind the swap it reports on (ADR-0030 decision 6).

    The premise is a load stalled inside the host: the manager holds the lease across the whole
    move and the scope is active, so a turn asking for the cortex at that instant genuinely
    cannot proceed, which is witnessed here before the report is read. That the read cannot
    block at all is the port's signature (a ``def``, not an ``async def``); what this pins is
    that it answers the truth at the worst moment, and it fails if the answer becomes a
    coroutine or a stale ``serving``.
    """
    host = ScriptedModelHost(running=["cortex"], pause_at=[("start", "brain")])
    manager = _manager(host)
    scope = _OpenScope(manager)
    async with asyncio.timeout(5.0):
        await host.reached[("start", "brain")].wait()
    waiting = asyncio.create_task(_lease(manager, "cortex"))
    await _settle()
    assert not waiting.done()
    assert manager.residency() == RESIDENCY_LOADING
    host.release[("start", "brain")].set()
    await scope.start()
    await scope.finish()
    async with asyncio.timeout(5.0):
        assert await waiting == _CORTEX_URL


async def test_a_claimed_handoff_still_reports_serving_because_the_cortex_still_serves() -> None:
    """The drain window still reports serving: nothing is unloaded and turns still run.

    ADR-0030 decision 6 keys not-ready on the cortex having stopped serving rather than on a
    handoff existing, so the report stays serving while delegated work quiesces and changes the
    moment something is actually evicted.
    """
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    async with manager.handoff_claim():
        assert manager.residency() == RESIDENCY_SERVING
        async with manager.acquire("cortex") as lease:  # and it really is still leasable
            assert lease.endpoint == _CORTEX_URL


def test_every_published_report_says_what_the_seam_and_the_human_actually_read() -> None:
    """The two fields, pinned against literals, because every case above pins them to themselves.

    ``assert manager.residency() == RESIDENCY_RESTORING`` proves the manager published *that*
    value and nothing whatsoever about what the value says, so flipping a ``serving`` or blanking
    a ``detail`` leaves every one of them passing while ``Health`` answers ready through the swap
    back and the overlay renders "The brain is not serving" with no reason after it. ``serving``
    is the whole verdict the seam maps to ``ready``; ``detail`` is the line the overlay shows
    verbatim, so it is app-authored user-facing text and belongs under the same gate as any
    other. Distinctness comes for free from pinning all six at once: identical blank details would
    collapse the swap windows into one report the tests above could no longer tell apart.
    """
    published = [
        RESIDENCY_SERVING,
        RESIDENCY_LOADING,
        RESIDENCY_DEEP,
        RESIDENCY_RESTORING,
        RESIDENCY_LOST,
        RESIDENCY_BOOT_FAILED,
    ]
    assert published == [
        ResidencyReport(serving=True, detail=""),
        ResidencyReport(
            serving=False, detail="swapping to the deep model; this takes a few minutes"
        ),
        ResidencyReport(serving=False, detail="a deep task is in progress"),
        ResidencyReport(serving=False, detail="bringing the usual assistant back"),
        ResidencyReport(
            serving=False,
            detail="the usual assistant could not be reloaded after a deep task; recovery is "
            "manual",
        ),
        ResidencyReport(
            serving=False,
            detail="the usual assistant did not come up at startup; the model host needs attention",
        ),
    ]


async def test_boot_recovery_s_observation_replaces_the_seed_a_fresh_manager_started_with() -> None:
    """A constructor cannot know what is on the GPU, so the first probe answers what recovery saw.

    Both directions matter: a boot that could not settle the cortex must stop the seam claiming
    readiness over a machine that serves nothing, and one that did settle it must publish that
    too rather than rely on the seed having been right by luck.
    """
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    await manager.publish_boot_residency(serving=False)
    assert manager.residency() == RESIDENCY_BOOT_FAILED
    await manager.publish_boot_residency(serving=True)
    assert manager.residency() == RESIDENCY_SERVING


async def test_a_boot_that_could_not_confirm_the_cortex_still_leases_a_working_one() -> None:
    """The boot report is display only: it must not refuse turns on a GPU that may be fine.

    Recovery failing to confirm the cortex is not the same as knowing it is gone. An unreachable
    supervisor says nothing about the process it supervises, and a load that outran its bound may
    still finish, so the lease keeps the forgiving posture boot recovery has always had while the
    dot goes amber. Clearing the resident here would turn one unanswered probe into a brain that
    refuses every turn until someone restarts it.
    """
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    await manager.publish_boot_residency(serving=False)
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


async def test_a_co_resident_plan_keeps_its_peers_through_a_handoff() -> None:
    """The ordinary handoff reconciles nothing, which is what a co-resident deployment needs.

    Converging is not a free question: it stops every evictable tier that is not already stopped
    and starts them all again, and this plan exists precisely to leave those peers serving through
    a swap. So the first daemon a manager meets is a seed and never a change, and this is what
    that rule buys.
    """
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"], boot_id="daemon-a")
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    await manager.publish_boot_residency(serving=True)
    async with manager.swap_scope("brain"):
        assert host.running == {"brain", "subagent-gpu"}
    assert ("stop", "subagent-gpu") not in host.calls


async def test_a_boot_that_could_not_reach_the_host_leaves_the_first_handoff_reconciling_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The seed can fail, and the rule that it is a seed is what covers the failure.

    Boot recovery is deliberately tolerant of a sidecar that is merely down, so the publish that
    seeds the watch can come back with no daemon named at all. The first daemon the next handoff
    meets is then the first this process has ever seen, and treating it as a replacement would
    converge a machine nobody has touched, taking down the very peers a co-resident plan keeps.
    """
    host = ScriptedModelHost(
        running=["cortex", "subagent-gpu"],
        boot_id="daemon-a",
        fail_once={("boot_id", ""): "connection refused"},
    )
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        await manager.publish_boot_residency(serving=False)
        async with manager.swap_scope("brain"):
            assert host.running == {"brain", "subagent-gpu"}
    assert "could not be asked which daemon is answering" in caplog.text
    assert ("stop", "subagent-gpu") not in host.calls


async def test_a_sidecar_that_restarted_since_the_boot_publish_is_reconciled_before_the_swap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The case the backlog entry described: a fresh daemon under a brain that never restarted.

    The replacement's boot default brings the cortex up and nothing else, so the standing peers
    this plan keeps co-resident are gone and the brain does not know. The next handoff asks who is
    answering, converges the machine back into the standing shape, and only then swaps: the peer
    is serving again inside the scope, having been started by the reconciliation rather than by
    anything in the swap, which for this plan stops nothing but the cortex.

    The seed is what makes it noticeable at all. Boot recovery published what it observed and
    recorded which daemon it observed it from, so this comparison has something on the other side
    of it from the very first handoff.
    """
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"], boot_id="daemon-a")
    manager = _manager(host, _plan(evict_models=("subagent-gpu",), coresident=True))
    await manager.publish_boot_residency(serving=True)
    # The sidecar is killed and revived: a new process, its own boot default, no peer tier.
    host.running = {"cortex"}
    host.boot = "daemon-b"
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency_watch"):
        async with manager.swap_scope("brain"):
            assert host.running == {"brain", "subagent-gpu"}
    assert "the model host has been replaced since the last handoff" in caplog.text
    assert host.running == {"cortex", "subagent-gpu"}


async def test_a_restarted_sidecar_whose_bounds_outlast_the_deadline_refuses_before_evicting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The pairing the composition root checked at boot, re-read on the one event that moves it.

    A restart is the only way the sidecar's env can change under a brain that never restarted, so
    it is the only place worth asking again. Refused here, the cortex has not been touched and the
    user is told the handoff did not happen; allowed through, the same deployment would abort an
    eviction that was working, minutes later, with the cortex already unloaded.
    """
    shipped = ControlBounds(probe_timeout_s=5.0, stop_grace_s=10.0, reap_timeout_s=30.0)
    host = ScriptedModelHost(running=["cortex"], boot_id="daemon-a", control_bounds=shipped)
    manager = _manager(host, _plan(control_deadline_s=60.0))
    await manager.publish_boot_residency(serving=True)
    host.boot = "daemon-b"
    host.bounds = ControlBounds(probe_timeout_s=5.0, stop_grace_s=20.0, reap_timeout_s=35.0)
    with (
        caplog.at_level(logging.ERROR, logger="cortex_core.residency_watch"),
        pytest.raises(SwapFailedError, match="no longer clears"),
    ):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    assert ("stop", "cortex") not in host.calls
    assert host.running == {"cortex"}
    assert "nothing was unloaded" in caplog.text
    # And the machine is still the one it was: the next turn leases the cortex as usual.
    async with manager.acquire("cortex") as lease:
        assert lease.endpoint == _CORTEX_URL


def test_the_manager_satisfies_every_port_it_is_composed_behind() -> None:
    """One object, three segregated protocols: the lease is unchanged, residency and its report."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    leasing: ModelManager = manager
    residency: ResidencyController = manager
    reporting: ResidencyReporter = manager
    assert leasing is residency is reporting
