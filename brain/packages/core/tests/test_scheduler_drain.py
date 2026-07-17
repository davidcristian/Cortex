"""One drain-semantics suite over BOTH SubagentScheduler implementations (ADR-0030 decision 4).

The pure budget scheduler and the admit-all fake must be observably interchangeable behind the
port's drain contract: refuse-not-queue while draining, a bounded wait for in-flight admissions,
nothing killed on timeout, and a reversible window (`undrain`). Every wait here is event-driven
and the timeout paths pass ``timeout_s=0.0`` (an already-expired bound), so no test sleeps
wall-clock; ``_settle`` yields the loop a few turns, which is scheduling, not time.

Distrust-green proofs (each mutation reddened the named test, then was restored):
- dropping the ``_draining`` check in ``admit`` (admissions allowed through a drain) reddens
  ``test_admit_is_refused_while_draining_until_undrain`` (both impls);
- dropping drain's ``notify_all`` (a queued waiter left sleeping) reddens
  ``test_a_spawn_waiting_on_a_full_budget_is_woken_and_refused_when_drain_begins``;
- making drain wait unbounded (no ``asyncio.timeout``) hangs, and returning True from its
  timeout path reddens ``test_drain_times_out_when_work_stays_in_flight_and_kills_nothing``;
- breaking ``undrain`` (window never released) reddens the same undrain-resumes assertions.
"""

import asyncio

import pytest

from cortex_core import (
    POOL_DRAINING_MSG,
    AdmitAllScheduler,
    PlacementRequest,
    ResourceBudgetScheduler,
    SubagentAdmissionError,
    SubagentScheduler,
)

_WHOLE_BUDGET = (4.0, 8.0)  # every "budget" fixture instance uses this cpu/mem pair


def _request(cpus: float = 1.0, memory_gb: float = 1.0) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=1.0, cpus=cpus, memory_gb=memory_gb)


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few turns so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


@pytest.fixture(params=["budget", "admit-all"])
def scheduler(request: pytest.FixtureRequest) -> SubagentScheduler:
    """A fresh scheduler of each implementation; every shared check runs against both."""
    if request.param == "budget":
        return ResourceBudgetScheduler(*_WHOLE_BUDGET)
    return AdmitAllScheduler()


class _Held:
    """One admission held open until told to finish, with its entry observable."""

    def __init__(self, scheduler: SubagentScheduler) -> None:
        self._scheduler = scheduler
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        async with self._scheduler.admit(_request()):
            self.entered.set()
            await self.release.wait()

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run())
        await self.entered.wait()

    async def finish(self) -> None:
        assert self.task is not None
        self.release.set()
        await self.task


async def test_drain_of_an_idle_pool_is_immediately_clean(scheduler: SubagentScheduler) -> None:
    """Nothing in flight means True at once, even under an already-expired bound."""
    assert await scheduler.drain(timeout_s=0.0) is True


async def test_admit_is_refused_while_draining_until_undrain(
    scheduler: SubagentScheduler,
) -> None:
    """The window refuses (typed, not queued) from drain until undrain, then admission resumes."""
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match="pool draining for a model handoff"):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_a_drain_refusal_reserves_nothing(scheduler: SubagentScheduler) -> None:
    """A refused admit charged nothing: after undrain the whole budget is still admissible."""
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request(*_WHOLE_BUDGET)):  # fits only if nothing leaked
        pass


async def test_drain_waits_for_an_in_flight_admission_and_resolves_on_release(
    scheduler: SubagentScheduler,
) -> None:
    """The bounded wait is event-driven: pending while work runs, True the moment it releases."""
    held = _Held(scheduler)
    await held.start()
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert not drain_task.done()  # one admission is still in flight, so the drain is pending
    await held.finish()
    assert await drain_task is True
    # A clean drain still holds the window until the conductor releases it.
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_drain_times_out_when_work_stays_in_flight_and_kills_nothing(
    scheduler: SubagentScheduler,
) -> None:
    """Timeout reports not-clean; the straggler runs on and the window holds until undrain."""
    held = _Held(scheduler)
    await held.start()
    assert await scheduler.drain(timeout_s=0.0) is False
    assert held.task is not None
    assert not held.task.done()  # nothing was killed: v1 never kills a subagent mid-stream
    with pytest.raises(SubagentAdmissionError, match="pool draining"):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    # The straggler's release is still accounted inside the window...
    await held.finish()
    # ...so a re-issued drain (a retried handoff) now resolves clean at once.
    assert await scheduler.drain(timeout_s=0.0) is True
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_in_flight_admissions_release_one_by_one_before_the_drain_resolves(
    scheduler: SubagentScheduler,
) -> None:
    """Each release re-checks the pool: the drain resolves only when the LAST one exits."""
    first, second = _Held(scheduler), _Held(scheduler)
    await first.start()
    await second.start()
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert not drain_task.done()
    await first.finish()
    await _settle()
    assert not drain_task.done()  # one straggler left; a partial release must not resolve it
    await second.finish()
    assert await drain_task is True
    scheduler.undrain()


async def test_concurrent_drains_settle_together(scheduler: SubagentScheduler) -> None:
    """Drain is idempotent: a second drain waits alongside the first, both resolve clean."""
    held = _Held(scheduler)
    await held.start()
    drains = [asyncio.create_task(scheduler.drain(timeout_s=60.0)) for _ in range(2)]
    await _settle()
    assert [task.done() for task in drains] == [False, False]
    await held.finish()
    assert [await task for task in drains] == [True, True]
    scheduler.undrain()
    scheduler.undrain()  # idempotent: releasing an already-released window is a no-op
    async with scheduler.admit(_request()):
        pass


async def test_undrain_without_a_drain_is_a_no_op(scheduler: SubagentScheduler) -> None:
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_a_spawn_waiting_on_a_full_budget_is_woken_and_refused_when_drain_begins() -> None:
    """The crux interleaving (budget impl only, since only it queues): the waiter must not sleep.

    A spawn queued on a transiently full budget when the drain begins would otherwise sleep
    through the whole handoff and admit into the brain phase on wake. Drain wakes it, it sees
    the window, and it refuses promptly, while the in-flight admission drains normally.
    """
    scheduler = ResourceBudgetScheduler(3.0, 100.0)
    holder = asyncio.Event()
    release = asyncio.Event()

    async def first() -> None:
        async with scheduler.admit(_request(cpus=2.0)):
            holder.set()
            await release.wait()

    async def second() -> None:
        async with scheduler.admit(_request(cpus=2.0)):
            pass  # pragma: no cover - refused at drain start, never admitted

    t1 = asyncio.create_task(first())
    await holder.wait()
    t2 = asyncio.create_task(second())
    await _settle()
    assert not t2.done()  # queued on the full budget (2 + 2 > 3), exactly the hazard case
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert t2.done()  # woken and refused NOW, not left sleeping until the budget frees
    with pytest.raises(SubagentAdmissionError, match="pool draining for a model handoff"):
        await t2
    assert not drain_task.done()  # the holder is still in flight, so the drain keeps waiting
    release.set()
    await t1
    assert await drain_task is True
    scheduler.undrain()


async def test_an_impossible_charge_keeps_its_own_refusal_during_a_drain() -> None:
    """The permanent wall precedes the transient window, so its message stays diagnostic."""
    scheduler = ResourceBudgetScheduler(*_WHOLE_BUDGET)
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match="exceeds the whole budget"):
        async with scheduler.admit(_request(cpus=99.0)):
            pass  # pragma: no cover - admit raises before the body runs


async def test_the_fake_records_admitted_requests_and_not_refused_ones() -> None:
    """The fake's observability hook: granted requests land in order, refusals never do."""
    scheduler = AdmitAllScheduler()
    small, large = _request(), _request(cpus=3.0)
    async with scheduler.admit(small), scheduler.admit(large):
        pass
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match=POOL_DRAINING_MSG):
        async with scheduler.admit(small):
            pass  # pragma: no cover - admit raises before the body runs
    assert scheduler.admitted == [small, large]
