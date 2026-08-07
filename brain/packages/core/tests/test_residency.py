"""SwappingModelManager: the unchanged lease, plus the one scope that changes residency.

The two halves are tested against each other on purpose, because their interaction is the whole
design: the swap happens only at a lease-free boundary, a queued acquire of another model waits
instead of failing, and the cortex restore lives in the scope's ``finally`` so it runs on
success, on a failed swap-in, on an exception, and under cancellation alike.

Every wait here is event-driven: leases are held open on ``asyncio.Event``s, readiness bounds
that must elapse are passed as ``load_timeout_s=0.0`` (already expired), and ``_settle`` yields
the loop a few turns, which is scheduling, not time. No test sleeps wall-clock.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- removing the ``finally`` around ``_restore`` (restoring only on the happy path) reddens
  ``test_a_failed_swap_in_still_restores_the_cortex``,
  ``test_an_exception_inside_the_scope_still_restores_the_cortex`` and
  ``test_cancelling_the_scope_still_restores_the_cortex``;
- swapping in without taking the lease first reddens
  ``test_the_swap_waits_for_the_in_flight_round_to_fall_free``, and taking the lease for the
  stops but not for the restore reddens
  ``test_the_restore_waits_for_the_new_resident_s_own_round``;
- awaiting the restore directly instead of shielding it (so a cancellation abandons it midway)
  reddens ``test_a_cancelled_scope_cannot_abandon_the_restore_halfway``;
- making ``_claim`` raise for a non-scope model instead of waiting reddens
  ``test_an_acquire_of_another_model_waits_out_the_scope_instead_of_failing``;
- dropping ``_end_scope``'s ``notify_all`` leaves a queued acquire asleep whenever the restore
  did not itself publish a residency change, which reddens
  ``test_a_queued_acquire_is_woken_even_when_the_swap_back_failed`` by timeout (the
  happy-path test alone does NOT discriminate it, which is why that second test exists);
- reading the claim and setting it two statements apart (an await between them) reddens the
  chaos suite's ``test_two_escalating_turns_racing_for_the_gpu_leave_one_of_them_untouched``, and
  dropping the refusal outright (``residency_claim.py``, where the rule now lives) reddens that
  case plus ``test_the_handoff_claim_refuses_a_second_holder_without_touching_the_host``;
- restarting nothing after the cortex comes back reddens
  ``test_the_scope_swaps_in_evicts_everything_else_and_restores_all_of_it``.

Three more for the residency report the seam publishes, each applied to production code alone
with the whole brain workspace re-run, so the counts are what actually reddened:

- answering from ``_resident`` instead of the report the swap publishes (the wrong source: it
  cannot tell a swap in from a swap back) reddens 5, the three report cases here plus
  ``test_health_reports_the_swap_window_it_is_in`` and
  ``test_health_tells_the_truth_about_residency_through_the_whole_wiring`` in the orchestrator.
  It does **not** discriminate the two stalled-load cases, because nothing is resident there
  either, which is why the restore and give-up cases exist beside them;
- dropping the give-up report (so a manager that stopped trying still says it is restoring)
  reddens exactly 1, ``test_a_restore_that_gave_up_stops_claiming_it_is_still_restoring``;
- publishing not-ready as soon as a handoff is claimed reddens exactly 1,
  ``test_a_claimed_handoff_still_reports_serving_because_the_cortex_still_serves``.

Four more, added because the three above pin only *which* value was published and nothing about
what it says: an audit measured that flipping ``RESIDENCY_RESTORING.serving`` or
``RESIDENCY_LOST.serving`` to ``True``, or blanking every not-serving ``detail``, left the whole
workspace green. Each below was applied to production code alone and the workspace re-run:

- ``serving=True`` on ``RESIDENCY_RESTORING`` reddens 2,
  ``test_every_published_report_says_what_the_seam_and_the_human_actually_read`` plus the seam's
  ``test_health_stays_not_ready_through_the_swap_back``; the same edit to ``RESIDENCY_LOST``
  reddens that first case plus ``test_health_stays_not_ready_after_a_restore_that_gave_up``, and
  to ``RESIDENCY_BOOT_FAILED`` that first case plus the composition root's boot case;
- blanking all five not-serving details reddens exactly 1, that same first case, which is also
  what keeps the four swap windows from collapsing into one indistinguishable report;
- dropping the not-serving branch of ``publish_boot_residency`` reddens 2,
  ``test_boot_recovery_s_observation_replaces_the_seed_a_fresh_manager_started_with`` and the
  composition root's boot case;
- clearing ``_resident`` in that publish (treating an unconfirmed boot as a known-dead GPU)
  reddens exactly 1, ``test_a_boot_that_could_not_confirm_the_cortex_still_leases_a_working_one``.
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
    """The evicted tier's restart is best effort, because the note for a failed restore lies here.

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
    """And refused as a handoff already in flight, never as a swap that broke.

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
    assert host.calls[:4] == [
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
    """Fail closed: a deployment that asked to be checked and cannot be is refused, not run."""
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
    with caplog.at_level(logging.WARNING, logger="cortex_core.residency"):
        async with manager.swap_scope("brain"):
            pass
    assert host.running == {"cortex"}
    assert host.calls.count(("start", "cortex")) == 2  # the failed attempt, then the retry
    assert [record.message for record in caplog.records] == [
        "the model host failed while restoring the cortex",
        "restoring the cortex failed; retrying",
    ]


async def test_a_restore_that_never_succeeds_raises_loudly_and_leaves_nothing_resident(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Past the retry only the runbook helps, so the failure is typed, logged, and honest."""
    host = ScriptedModelHost(running=["cortex"], fail={("start", "cortex"): "no such device"})
    manager = _manager(host)
    with (
        caplog.at_level(logging.WARNING, logger="cortex_core.residency"),
        pytest.raises(ResidencyRestoreError, match="manual recovery is needed"),
    ):
        async with manager.swap_scope("brain"):
            pass
    assert host.calls.count(("start", "cortex")) == 2
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    # Nothing is resident, so an acquire says so rather than leasing a dead endpoint.
    with pytest.raises(ModelUnavailableError, match="resident: None"):
        async with manager.acquire("cortex"):
            pass  # pragma: no cover - acquire raises before the body runs


async def test_a_restore_whose_gate_never_reports_ready_also_gives_up() -> None:
    """The restore's failure is not only a raising host: a cortex stuck loading counts too."""
    host = ScriptedModelHost(running=["cortex"], status_override={"cortex": ModelHostState.LOADING})
    manager = _manager(host, _plan(load_timeout_s=0.0))
    with pytest.raises(ResidencyRestoreError):
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
    """The swap back is its own answer: nothing is resident either way, and they read apart."""
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
    """The one honest answer that outlives its turn: nothing is resident and no retry is left.

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
    that it answers the truth at the worst moment, and it reddens if the answer becomes a
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
    """The drain window is deliberately green: nothing is unloaded and turns still run.

    ADR-0030 decision 6 keys not-ready on the cortex having stopped serving, not on a handoff
    existing, so the indicator stays green while delegated work quiesces and turns the moment
    something is actually evicted.
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
    a ``detail`` leaves every one of them green while ``Health`` answers ready through the swap
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


def test_the_manager_satisfies_every_port_it_is_composed_behind() -> None:
    """One object, three segregated protocols: the lease is unchanged, residency and its report."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    leasing: ModelManager = manager
    residency: ResidencyController = manager
    reporting: ResidencyReporter = manager
    assert leasing is residency is reporting
