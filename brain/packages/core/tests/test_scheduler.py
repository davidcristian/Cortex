"""Behavior tests for ConcurrencyScheduler: the bounded CPU admission gate (ADR-0010)."""

import asyncio

import pytest

from cortex_core import ConcurrencyScheduler


async def test_admit_grants_and_releases_a_slot() -> None:
    entered = False
    async with ConcurrencyScheduler(1).admit():
        entered = True
    assert entered


@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_nonpositive_concurrency(bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        ConcurrencyScheduler(bad)


async def test_admit_bounds_concurrency_to_the_cap() -> None:
    sched = ConcurrencyScheduler(1)
    order: list[str] = []
    first_holds = asyncio.Event()
    release_first = asyncio.Event()

    async def first() -> None:
        async with sched.admit():
            order.append("first-in")
            first_holds.set()
            await release_first.wait()
            order.append("first-out")

    async def second() -> None:
        async with sched.admit():
            order.append("second-in")

    t1 = asyncio.create_task(first())
    await first_holds.wait()  # first owns the only slot
    t2 = asyncio.create_task(second())
    await asyncio.sleep(0)  # give second a turn. It must block on the full budget
    assert order == ["first-in"]
    release_first.set()
    await asyncio.gather(t1, t2)
    # second only ran after first freed its slot.
    assert order == ["first-in", "first-out", "second-in"]
