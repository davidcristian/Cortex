"""Behavior tests for ResourceBudgetScheduler: the soft 2-D CPU/RAM budget (ADR-0012)."""

import asyncio

import pytest

from cortex_core import PlacementRequest, ResourceBudgetScheduler, SubagentScheduler


def _request(cpus: float, memory_gb: float) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=1.0, cpus=cpus, memory_gb=memory_gb)


def test_scheduler_satisfies_the_port() -> None:
    """The concrete scheduler is a structural SubagentScheduler (pins the port signature)."""
    scheduler: SubagentScheduler = ResourceBudgetScheduler(4.0, 8.0)
    assert isinstance(scheduler, ResourceBudgetScheduler)


async def test_admit_grants_and_releases_a_slot() -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    entered = False
    async with scheduler.admit(_request(2.0, 2.0)):
        entered = True
    assert entered
    # The reservation was released, so a second admit fits immediately (no wait).
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
    [(5.0, 1.0), (1.0, 9.0)],  # cpus over the whole cpu budget; memory over the whole mem budget
)
async def test_a_charge_over_the_whole_budget_is_rejected(cpus: float, memory_gb: float) -> None:
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    with pytest.raises(ValueError, match="exceeds the whole budget"):
        async with scheduler.admit(_request(cpus, memory_gb)):
            pass  # pragma: no cover - admit raises before the body runs


async def _blocks_until_first_releases(
    scheduler: ResourceBudgetScheduler, req: PlacementRequest
) -> None:
    """Assert a second `req` admit queues behind a held one and only runs once it releases."""
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

    t1 = asyncio.create_task(first())
    await first_holds.wait()  # first owns enough of the budget to block a second identical ask
    t2 = asyncio.create_task(second())
    await asyncio.sleep(0)  # give second a turn. It must block on the full budget
    assert order == ["first-in"]
    release_first.set()
    await asyncio.gather(t1, t2)
    assert order == ["first-in", "first-out", "second-in"]


async def test_admit_queues_when_the_cpu_budget_is_full() -> None:
    # cpu is the binding constraint (2 + 2 > 3); memory has room to spare.
    await _blocks_until_first_releases(ResourceBudgetScheduler(3.0, 100.0), _request(2.0, 1.0))


async def test_admit_queues_when_the_memory_budget_is_full() -> None:
    # memory is the binding constraint (2 + 2 > 3); cpu has room to spare.
    await _blocks_until_first_releases(ResourceBudgetScheduler(100.0, 3.0), _request(1.0, 2.0))
