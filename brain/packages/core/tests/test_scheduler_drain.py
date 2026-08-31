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

_WHOLE_BUDGET = (4.0, 8.0)  # the cpu and memory pair every budget fixture here is built with


def _request(cpus: float = 1.0, memory_gb: float = 1.0) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=1.0, cpus=cpus, memory_gb=memory_gb)


async def _settle(turns: int = 5) -> None:
    """Yield the event loop a few times so spawned tasks reach their next suspension point."""
    for _ in range(turns):
        await asyncio.sleep(0)


@pytest.fixture(params=["budget", "admit-all"])
def scheduler(request: pytest.FixtureRequest) -> SubagentScheduler:
    """A fresh scheduler of each implementation; every shared check runs against both."""
    if request.param == "budget":
        return ResourceBudgetScheduler(*_WHOLE_BUDGET)
    return AdmitAllScheduler()


class _Held:
    """One admission held open until told to finish, with its task available to the test."""

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
    assert await scheduler.drain(timeout_s=0.0) is True


async def test_admit_is_refused_while_draining_until_undrain(
    scheduler: SubagentScheduler,
) -> None:
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match="pool draining for a model handoff"):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_a_drain_refusal_reserves_nothing(scheduler: SubagentScheduler) -> None:
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request(*_WHOLE_BUDGET)):
        pass


async def test_drain_waits_for_an_in_flight_admission_and_resolves_on_release(
    scheduler: SubagentScheduler,
) -> None:
    held = _Held(scheduler)
    await held.start()
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert not drain_task.done()
    await held.finish()
    assert await drain_task is True
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_drain_times_out_when_work_stays_in_flight_and_kills_nothing(
    scheduler: SubagentScheduler,
) -> None:
    held = _Held(scheduler)
    await held.start()
    assert await scheduler.drain(timeout_s=0.0) is False
    assert held.task is not None
    assert not held.task.done()
    with pytest.raises(SubagentAdmissionError, match="pool draining"):
        async with scheduler.admit(_request()):
            pass  # pragma: no cover - admit raises before the body runs
    await held.finish()
    assert await scheduler.drain(timeout_s=0.0) is True
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_in_flight_admissions_release_one_by_one_before_the_drain_resolves(
    scheduler: SubagentScheduler,
) -> None:
    first, second = _Held(scheduler), _Held(scheduler)
    await first.start()
    await second.start()
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert not drain_task.done()
    await first.finish()
    await _settle()
    assert not drain_task.done()
    await second.finish()
    assert await drain_task is True
    scheduler.undrain()


async def test_concurrent_drains_settle_together(scheduler: SubagentScheduler) -> None:
    held = _Held(scheduler)
    await held.start()
    drains = [asyncio.create_task(scheduler.drain(timeout_s=60.0)) for _ in range(2)]
    await _settle()
    assert [task.done() for task in drains] == [False, False]
    await held.finish()
    assert [await task for task in drains] == [True, True]
    scheduler.undrain()
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_undrain_without_a_drain_is_a_no_op(scheduler: SubagentScheduler) -> None:
    scheduler.undrain()
    async with scheduler.admit(_request()):
        pass


async def test_a_spawn_waiting_on_a_full_budget_is_woken_and_refused_when_drain_begins() -> None:
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
    assert not t2.done()
    drain_task = asyncio.create_task(scheduler.drain(timeout_s=60.0))
    await _settle()
    assert t2.done()
    with pytest.raises(SubagentAdmissionError, match="pool draining for a model handoff"):
        await t2
    assert not drain_task.done()
    release.set()
    await t1
    assert await drain_task is True
    scheduler.undrain()


async def test_an_impossible_charge_keeps_its_own_refusal_during_a_drain() -> None:
    scheduler = ResourceBudgetScheduler(*_WHOLE_BUDGET)
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match="exceeds the whole budget"):
        async with scheduler.admit(_request(cpus=99.0)):
            pass  # pragma: no cover - admit raises before the body runs


async def test_the_fake_records_admitted_requests_and_not_refused_ones() -> None:
    scheduler = AdmitAllScheduler()
    small, large = _request(), _request(cpus=3.0)
    async with scheduler.admit(small), scheduler.admit(large):
        pass
    assert await scheduler.drain(timeout_s=0.0) is True
    with pytest.raises(SubagentAdmissionError, match=POOL_DRAINING_MSG):
        async with scheduler.admit(small):
            pass  # pragma: no cover - admit raises before the body runs
    assert scheduler.admitted == [small, large]
