import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest

from cortex_core import (
    ATTEMPTS_PER_ADMISSION,
    DEFAULT_ADMISSION_WAIT_S,
    DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
    MAX_SPAWN_BATCH,
    PlacementRequest,
    ResourceBudgetScheduler,
    SubagentAdmissionError,
    SubagentScheduler,
)

# Every test that can queue runs under this bound: the defect under test is an unbounded wait,
# and a change that brought it back would hang the suite instead of failing.
_SUITE_BOUND_S = 10.0


def _request(cpus: float, memory_gb: float) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=1.0, cpus=cpus, memory_gb=memory_gb)


def test_scheduler_satisfies_the_port() -> None:
    scheduler: SubagentScheduler = ResourceBudgetScheduler(4.0, 8.0)
    assert isinstance(scheduler, ResourceBudgetScheduler)


async def test_admit_grants_and_releases_a_slot() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    entered = False
    async with scheduler.admit(_request(2.0, 2.0)):
        entered = True
    assert entered
    async with scheduler.admit(_request(4.0, 8.0)):
        pass


@pytest.mark.parametrize(
    ("cpu_budget", "mem_budget"), [(0.0, 8.0), (-1.0, 8.0), (4.0, 0.0), (4.0, -1.0)]
)
def test_rejects_nonpositive_budget(cpu_budget: float, mem_budget: float) -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        ResourceBudgetScheduler(cpu_budget, mem_budget)


@pytest.mark.parametrize(
    ("cpus", "memory_gb"),
    [(5.0, 1.0), (1.0, 9.0)],
)
async def test_a_charge_over_the_whole_budget_is_rejected(cpus: float, memory_gb: float) -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    with pytest.raises(SubagentAdmissionError, match="exceeds the whole budget"):
        async with scheduler.admit(_request(cpus, memory_gb)):
            pass  # pragma: no cover - admit raises before the body runs


async def test_a_charge_equal_to_the_whole_budget_is_admitted() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    async with scheduler.admit(_request(4.0, 8.0)):
        pass


async def test_a_refused_charge_reserves_nothing() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request(5.0, 1.0)):
            pass  # pragma: no cover - admit raises before the body runs
    async with scheduler.admit(_request(4.0, 8.0)):
        pass


async def _blocks_until_first_releases(
    scheduler: ResourceBudgetScheduler, req: PlacementRequest
) -> None:
    """Check that a second ``req`` queues behind a held one and runs only once it is released."""
    order: list[str] = []
    first_holds = asyncio.Event()
    release_first = asyncio.Event()

    async def first() -> None:
        async with scheduler.admit(req):
            order.append("first-in")
            first_holds.set()
            await release_first.wait()
            order.append("first-out")

    async def second() -> None:
        async with scheduler.admit(req):
            order.append("second-in")

    async with asyncio.timeout(_SUITE_BOUND_S):
        t1 = asyncio.create_task(first())
        await first_holds.wait()
        t2 = asyncio.create_task(second())
        await asyncio.sleep(0)
        assert order == ["first-in"]
        release_first.set()
        await asyncio.gather(t1, t2)
    assert order == ["first-in", "first-out", "second-in"]


async def test_admit_queues_when_the_cpu_budget_is_full() -> None:
    await _blocks_until_first_releases(ResourceBudgetScheduler(3.0, 100.0), _request(2.0, 1.0))


async def test_admit_queues_when_the_memory_budget_is_full() -> None:
    await _blocks_until_first_releases(ResourceBudgetScheduler(100.0, 3.0), _request(1.0, 2.0))


@asynccontextmanager
async def _peer_holding(
    scheduler: ResourceBudgetScheduler, req: PlacementRequest
) -> AsyncGenerator[None]:
    """Hold ``req``'s charge in another task for the block, so an equal request has to queue."""
    holding = asyncio.Event()
    release = asyncio.Event()

    async def peer() -> None:
        async with scheduler.admit(req):
            holding.set()
            await release.wait()

    task = asyncio.create_task(peer())
    await holding.wait()
    try:
        yield
    finally:
        release.set()
        await task


async def test_a_wait_that_outlasts_the_bound_is_refused_and_names_it() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S), _peer_holding(scheduler, _request(4.0, 8.0)):
        with pytest.raises(SubagentAdmissionError, match="waited 0s for room"):
            async with scheduler.admit(_request(4.0, 8.0)):
                pass  # pragma: no cover - admit raises before the body runs


async def test_a_zero_bound_still_admits_what_fits_right_now() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S), scheduler.admit(_request(4.0, 8.0)):
        pass


async def test_a_wait_refused_at_the_bound_reserves_nothing() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S):
        async with _peer_holding(scheduler, _request(2.0, 2.0)):
            with pytest.raises(SubagentAdmissionError):
                async with scheduler.admit(_request(4.0, 8.0)):
                    pass  # pragma: no cover - admit raises before the body runs
        async with scheduler.admit(_request(4.0, 8.0)):
            pass


def test_rejects_a_negative_wait_bound() -> None:
    with pytest.raises(ValueError, match="wait_timeout_s must be >= 0"):
        ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=-1.0)


def test_the_default_bound_clears_both_the_measured_batch_wait_and_the_longest_hold() -> None:
    serial_batch_wait_s = 1624.6
    overlapped_batch_wait_s = 893.2
    assert MAX_SPAWN_BATCH == 8  # the batch size both waits above were measured at
    assert overlapped_batch_wait_s < serial_batch_wait_s
    hold_s = ATTEMPTS_PER_ADMISSION * DEFAULT_SUBAGENT_RUN_TIMEOUT_S
    assert hold_s == 4800.0
    assert 2 * serial_batch_wait_s < DEFAULT_ADMISSION_WAIT_S
    assert hold_s < DEFAULT_ADMISSION_WAIT_S
    assert DEFAULT_ADMISSION_WAIT_S == 3 * DEFAULT_SUBAGENT_RUN_TIMEOUT_S == 7200.0
