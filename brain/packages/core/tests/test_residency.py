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
  happy-path test alone does NOT discriminate it, which is why that second test exists).
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    ModelHost,
    ModelHostState,
    ModelManager,
    ModelUnavailableError,
    RecordingSleeper,
    ResidencyController,
    ResidencyPlan,
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
        "evict_models": ("subagent-gpu",),
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


async def test_the_scope_swaps_in_evicts_everything_else_and_serves_the_new_resident() -> None:
    """Decision 4 step 3's ordering, read straight off the host's op log."""
    host = ScriptedModelHost(running=["cortex", "subagent-gpu"])
    manager = _manager(host)
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
    ]
    assert host.running == {"cortex"}
    async with manager.acquire("cortex") as lease:  # the cortex serves again, unchanged
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
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    scope = _OpenScope(manager)
    await scope.start()
    with pytest.raises(SwapFailedError, match="already active"):
        async with manager.swap_scope("brain"):
            pass  # pragma: no cover - entering raises before the body runs
    await scope.finish()


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


def test_the_manager_satisfies_both_ports() -> None:
    """One object, two segregated protocols: the lease port is unchanged, residency is new."""
    manager = _manager(ScriptedModelHost(running=["cortex"]))
    leasing: ModelManager = manager
    residency: ResidencyController = manager
    assert leasing is residency
