"""Behavior tests for ResourceBudgetScheduler: the soft 2-D CPU/RAM budget (ADR-0012)."""

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

# Every test that can queue is wrapped in this, because the defect under test is an unbounded
# wait: a mutation that restores it would hang the suite, and a hung suite proves nothing.
_SUITE_BOUND_S = 10.0


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
    """The budget's one wall: refused outright, not queued, and typed so the runner can catch it."""
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    with pytest.raises(SubagentAdmissionError, match="exceeds the whole budget"):
        async with scheduler.admit(_request(cpus, memory_gb)):
            pass  # pragma: no cover - admit raises before the body runs


async def test_a_charge_equal_to_the_whole_budget_is_admitted() -> None:
    """The wall is strictly "larger than", so the biggest admissible spawn runs (alone)."""
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    async with scheduler.admit(_request(4.0, 8.0)):
        pass


async def test_a_refused_charge_reserves_nothing() -> None:
    """The wall refuses before charging, so it cannot leak budget the refused spawn never got."""
    scheduler = ResourceBudgetScheduler(4.0, 8.0)
    with pytest.raises(SubagentAdmissionError):
        async with scheduler.admit(_request(5.0, 1.0)):
            pass  # pragma: no cover - admit raises before the body runs
    async with scheduler.admit(_request(4.0, 8.0)):  # the whole budget is still free
        pass


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

    async with asyncio.timeout(_SUITE_BOUND_S):
        t1 = asyncio.create_task(first())
        await first_holds.wait()  # first owns enough of the budget to block a second identical ask
        t2 = asyncio.create_task(second())
        await asyncio.sleep(0)  # give second a turn. It must block on the full budget
        assert order == ["first-in"]
        release_first.set()
        await asyncio.gather(t1, t2)
    assert order == ["first-in", "first-out", "second-in"]


async def test_admit_queues_when_the_cpu_budget_is_full() -> None:
    # cpu is the binding constraint (2 + 2 > 3); memory has room to spare. The default bound is
    # the one in force here: a waiter the budget frees is admitted, never refused for having
    # queued at all.
    await _blocks_until_first_releases(ResourceBudgetScheduler(3.0, 100.0), _request(2.0, 1.0))


async def test_admit_queues_when_the_memory_budget_is_full() -> None:
    # memory is the binding constraint (2 + 2 > 3); cpu has room to spare.
    await _blocks_until_first_releases(ResourceBudgetScheduler(100.0, 3.0), _request(1.0, 2.0))


@asynccontextmanager
async def _peer_holding(
    scheduler: ResourceBudgetScheduler, req: PlacementRequest
) -> AsyncGenerator[None]:
    """Hold ``req``'s charge in another task for the block, so an equal ask has to queue."""
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
    """The queue stopped being forever: the bound elapses and the wait becomes a typed refusal.

    An already-expired bound drives the timeout path, exactly as `drain`'s own bound is driven,
    so nothing here spends wall-clock time proving it. The message carries this scheduler's
    seconds, not a literal: a refusal that misreports the bound sends its reader to the wrong
    knob.
    """
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S), _peer_holding(scheduler, _request(4.0, 8.0)):
        with pytest.raises(SubagentAdmissionError, match="waited 0s for room"):
            async with scheduler.admit(_request(4.0, 8.0)):
                pass  # pragma: no cover - admit raises before the body runs


async def test_a_zero_bound_still_admits_what_fits_right_now() -> None:
    """Zero means never queue, not never admit: the bound is on the wait, never on the charge."""
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S), scheduler.admit(_request(4.0, 8.0)):
        pass


async def test_a_wait_refused_at_the_bound_reserves_nothing() -> None:
    """The bound refuses before charging, so a timed-out waiter cannot leak budget behind it."""
    scheduler = ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=0.0)
    async with asyncio.timeout(_SUITE_BOUND_S):
        async with _peer_holding(scheduler, _request(2.0, 2.0)):
            with pytest.raises(SubagentAdmissionError):
                async with scheduler.admit(_request(4.0, 8.0)):
                    pass  # pragma: no cover - admit raises before the body runs
        async with scheduler.admit(_request(4.0, 8.0)):  # the whole budget came back
            pass


def test_rejects_a_negative_wait_bound() -> None:
    """A negative bound would refuse every queued spawn while reading like a generous one."""
    with pytest.raises(ValueError, match="wait_timeout_s must be >= 0"):
        ResourceBudgetScheduler(4.0, 8.0, wait_timeout_s=-1.0)


def test_the_default_bound_clears_both_the_measured_batch_wait_and_the_longest_hold() -> None:
    """Pinned against both halves of its derivation and against the literal (ADR-0012 addenda).

    The bound answers two questions and the larger one wins. The first is how long a batch that is
    working can legitimately keep its last spawn queued: measured on a live full batch of this
    size, that is 1624.6 s while an entry's admitted pair serializes on one placement target and
    893.2 s while it overlaps, and a bound under twice the serial figure would refuse work that was
    going to run. The second is how long one task can hold the room that queue is waiting for,
    which is `ATTEMPTS_PER_ADMISSION` whole run deadlines, since a GPU-placed inference failure is
    re-run once on the CPU inside the same admission under a deadline armed fresh. At the shipped
    deadline the hold is the larger, so the bound is stated in deadlines: three of them, the two a
    task can spend plus one of margin.

    The measured figures are pinned as the constants they are rather than recomputed, because a
    measurement is not arithmetic; what is asserted is that the shipped bound still clears both.
    The batch size is asserted too, since a different cap is a different measurement.
    """
    serial_batch_wait_s = 1624.6
    overlapped_batch_wait_s = 893.2
    assert MAX_SPAWN_BATCH == 8  # the shape both figures were measured at
    assert overlapped_batch_wait_s < serial_batch_wait_s  # the placement that binds is the serial
    hold_s = ATTEMPTS_PER_ADMISSION * DEFAULT_SUBAGENT_RUN_TIMEOUT_S
    assert hold_s == 4800.0
    assert 2 * serial_batch_wait_s < DEFAULT_ADMISSION_WAIT_S
    assert hold_s < DEFAULT_ADMISSION_WAIT_S
    assert DEFAULT_ADMISSION_WAIT_S == 3 * DEFAULT_SUBAGENT_RUN_TIMEOUT_S == 7200.0
