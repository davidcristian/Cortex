"""A peer the swap back could not restart: the record, the placer it closes, and the retry.

The unit under test is the whole path the ADR-0030 tier-outage addendum describes, because no
part of it is worth anything alone: a record nothing reads is a set, a closed placer nothing
writes is a dead branch, and a retry with no mark to clear never runs. So the cases here drive
the real ``SwappingModelManager`` over the scripted host with a real ``VramBudgetPlacer``, and
ask where a spawn would land and what a probe would read at each point.

The distinction every case is really about: a tier stopped **on purpose** while the deep model
holds the card is not a tier that is **down**, and only the second one closes the GPU or reaches
the seam. ``test_an_evicted_tier_is_not_a_missing_one`` is that sentence as an assertion.

Distrust-green proofs (each mutation applied to production code alone, the whole brain workspace
re-run, then reverted, so the counts are measured rather than aimed at):
- dropping ``tiers.mark_missing`` from ``residency_moves._restart_evicted`` reddens 7, six here
  (every case that asks where a spawn lands or what a probe reads after a failed restart) plus
  ``test_health_stays_ready_and_names_a_peer_tier_that_did_not_come_back`` at the seam;
- dropping ``tiers.mark_standing`` from the same loop's ``else`` reddens 1,
  ``test_a_second_handoff_that_restarts_the_peer_reopens_the_gpu``;
- reopening on any ``mark_standing`` rather than on an emptied record reddens 1,
  ``test_one_peer_back_of_two_keeps_the_gpu_closed``;
- annotating a not-serving report in ``StandingTiers.note_on`` reddens 1,
  ``test_an_evicted_tier_is_not_a_missing_one``, which is the down-versus-evicted rule itself;
- consulting the headroom before the closed flag in ``VramBudgetPlacer.place`` reddens 7, five
  here and two in test_placer.py;
- starting a tier that reports ``LOADING`` reddens 1,
  ``test_a_retry_leaves_a_tier_that_is_still_loading_alone``;
- dropping the scope guard in ``heal_standing_tiers`` reddens 1,
  ``test_a_retry_defers_while_a_handoff_owns_the_gpu``;
- dropping the pass guard in ``TierHealer.run`` reddens 1,
  ``test_a_failing_pass_costs_one_pass_and_not_the_loop``, on its own bound rather than by
  hanging, which is why every wait in this file is inside an ``asyncio.timeout``.

One case here was vacuous when it was written and the mutation table is what found it:
``test_a_peer_that_would_not_restart_closes_gpu_placement`` held its first placement's 2.0 GiB
against a 3.0 GiB headroom, so the spawn it asserted on spilled for want of room whatever the
record said, and dropping ``mark_missing`` left it green. It releases now.
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest

from cortex_core import (
    RESIDENCY_DEEP,
    RESIDENCY_SERVING,
    TIERS_MISSING_DETAIL,
    ModelHostState,
    PlacementRequest,
    PlacementTarget,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    StandingTiers,
    SwappingModelManager,
    TierHealer,
    VramBudgetPlacer,
    retry_missing,
)

_ENDPOINTS = {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"}
_TIER = "subagent-gpu"
_OTHER_TIER = "subagent-gpu-2"
_RETRY_LOGGER = "cortex_core.residency_tiers"
_LOOP_NAME = "residency-tier-healer"


def _retry_log(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Only the retry's own lines: a case that swapped first also captured the swap's failure."""
    return [record.msg for record in caplog.records if record.name == _RETRY_LOGGER]


class _FixedClock:
    """A clock that never advances; nothing here waits on one."""

    def now(self) -> datetime:
        return datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "evict_models": (_TIER,),
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _placer() -> VramBudgetPlacer:
    """Headroom 3.0 GiB beside the cortex, so the 2.0 GiB spawn below lands on the GPU."""
    return VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0)


def _spawn() -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=2.0, cpus=1.0, memory_gb=1.0)


def _manager(
    host: ScriptedModelHost,
    placer: VramBudgetPlacer | None = None,
    plan: ResidencyPlan | None = None,
) -> SwappingModelManager:
    return SwappingModelManager(
        host,
        _ENDPOINTS,
        plan if plan is not None else _plan(),
        _FixedClock(),
        RecordingSleeper(),
        placer,
    )


async def test_a_peer_that_would_not_restart_closes_gpu_placement() -> None:
    """The entry's whole harm: admission reopens, and the next spawn is sent to a dead server.

    The re-place on a failed GPU attempt makes that spawn survive, but it pays two loads to
    learn what the swap back already knew. Once the record exists, the placer skips the tier and
    the spawn goes to the CPU first time.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, placer)
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    # Released, or the second ask below would spill for want of headroom and prove nothing: the
    # ledger holds 2.0 of the 3.0 GiB and this file's whole point is placement that ignores it.
    placer.release(before)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_peer_that_came_back_leaves_placement_where_it_found_it() -> None:
    """The ordinary swap back: nothing is missing, so nothing is closed."""
    placer = _placer()
    manager = _manager(ScriptedModelHost(running=["cortex", _TIER]), placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert manager.residency() == RESIDENCY_SERVING


async def test_the_seam_says_which_peer_is_down_while_the_cortex_serves() -> None:
    """Legible rather than silent, on the surface that already reaches the overlay's tooltip."""
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    report = manager.residency()
    assert report.serving is True  # turns still run; this is not a swap window
    assert report.detail == TIERS_MISSING_DETAIL.format(models=_TIER)


async def test_an_evicted_tier_is_not_a_missing_one() -> None:
    """Down versus stopped on purpose, which is the distinction the whole record turns on.

    A peer is stopped for the length of every handoff, and the report already says a swap is in
    flight. Annotating that would call the swap a fault and would put two different sentences
    about the same tier on one probe.
    """
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    assert manager.residency().detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    async with manager.swap_scope("brain"):
        # The tier is stopped again here, and known missing besides. The window's own words win.
        assert manager.residency() == RESIDENCY_DEEP


async def test_a_second_handoff_that_restarts_the_peer_reopens_the_gpu() -> None:
    """A successful start is a clearing path, so a handoff that works undoes a handoff that did."""
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert manager.residency() == RESIDENCY_SERVING


async def test_one_peer_back_of_two_keeps_the_gpu_closed() -> None:
    """The placer holds one bit for the card, so the last missing tier is what reopens it."""
    placer = _placer()
    tiers = StandingTiers(placer)
    tiers.mark_missing(_TIER)
    tiers.mark_missing(_OTHER_TIER)
    tiers.mark_standing(_TIER)
    assert tiers.missing == (_OTHER_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    tiers.mark_standing(_OTHER_TIER)
    assert tiers.missing == ()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


def test_a_deployment_with_no_pool_still_records_which_peer_is_down() -> None:
    """``None`` places nothing, so the record still stands and there is nothing to close."""
    tiers = StandingTiers()
    assert tiers.placer is None
    tiers.mark_missing(_TIER)
    assert tiers.missing == (_TIER,)
    assert tiers.note_on(RESIDENCY_SERVING).detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    tiers.mark_standing(_TIER)
    assert tiers.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


def test_marking_a_tier_standing_that_was_never_missing_changes_nothing() -> None:
    """The restart loop calls this for every peer it started, most of which were never down."""
    placer = _placer()
    tiers = StandingTiers(placer)
    tiers.mark_standing(_TIER)
    assert tiers.missing == ()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_retry_that_finds_the_tier_serving_reopens_the_gpu(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The clearing path the record owes, since the next handoff may be hours away.

    Two passes by design: the first finds the tier stopped and asks for it, the second observes
    it serving. Readiness is never gated inside a pass, so a tier that takes minutes to load
    costs the loop nothing while it does.
    """
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.calls.clear()
    await manager.heal_standing_tiers()  # finds it stopped, asks for it back
    assert host.calls == [("status", _TIER), ("start", _TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.CPU  # not yet observed serving
    with caplog.at_level(logging.INFO, logger=_RETRY_LOGGER):
        await manager.heal_standing_tiers()
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert _retry_log(caplog) == ["a tier the standing residency was missing is serving again"]


async def test_a_retry_leaves_a_tier_that_is_still_loading_alone() -> None:
    """A load in flight is neither a failure to retry nor a tier to reopen the GPU for."""
    host = ScriptedModelHost(running=[_TIER], status_override={_TIER: ModelHostState.LOADING})
    tiers = StandingTiers(_placer())
    tiers.mark_missing(_TIER)
    await retry_missing(host, tiers)
    assert host.calls == [("status", _TIER)]  # asked, and deliberately not started again
    assert tiers.missing == (_TIER,)


async def test_a_retry_that_cannot_reach_the_host_leaves_the_record_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pass never raises: one unreachable tier must not stop the others being retried."""
    placer = _placer()
    host = ScriptedModelHost(
        running=["cortex", _TIER],
        fail={("start", _TIER): "no such device", ("status", _TIER): "connection refused"},
    )
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await manager.heal_standing_tiers()
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert _retry_log(caplog) == [
        "a tier the standing residency is missing could not be retried: model=%s error=%s"
    ]


async def test_a_retry_defers_while_a_handoff_owns_the_gpu() -> None:
    """Starting a peer while the deep model is alone on the card is the one forbidden move."""
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    async with manager.swap_scope("brain"):
        host.calls.clear()
        await manager.heal_standing_tiers()
        assert host.calls == []


async def test_the_loop_keeps_retrying_until_it_is_closed() -> None:
    """``TierHealer`` is the pacing and the task; a pass is whatever it was handed."""
    passes = asyncio.Event()
    count = 0

    async def one_pass() -> None:
        nonlocal count
        count += 1
        if count >= 2:
            passes.set()

    healer = TierHealer(one_pass, interval_s=0.001)
    healer.start()
    healer.start()  # idempotent: the second call must not put a second loop on the same record
    assert len([task for task in asyncio.all_tasks() if task.get_name() == _LOOP_NAME]) == 1
    try:
        async with asyncio.timeout(5.0):
            await passes.wait()
    finally:
        await healer.aclose()
    assert count >= 2


async def test_a_failing_pass_costs_one_pass_and_not_the_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug nobody enumerated must cost a retry, never the retrying a degraded stack waits on."""
    survived = asyncio.Event()
    calls = 0

    async def flaky() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "an unenumerated bug"
            raise RuntimeError(msg)
        survived.set()

    healer = TierHealer(flaky, interval_s=0.001)
    with caplog.at_level(logging.ERROR, logger="cortex_core.residency_heal"):
        healer.start()
        try:
            async with asyncio.timeout(5.0):
                await survived.wait()
        finally:
            await healer.aclose()
    assert [record.message for record in caplog.records] == [
        "a residency tier retry failed; the next pass tries again"
    ]


async def test_closing_wakes_the_wait_instead_of_serving_out_the_interval() -> None:
    """Shutdown must not be held for the pacing, which is why the wait is on the stop signal."""
    entered = asyncio.Event()

    async def one_pass() -> None:
        entered.set()

    healer = TierHealer(one_pass, interval_s=3600.0)
    healer.start()
    async with asyncio.timeout(5.0):
        await entered.wait()
        await healer.aclose()  # would sit out the hour if the wait were a plain sleep


async def test_closing_a_loop_that_never_started_is_a_no_op() -> None:
    """The uniform shutdown hook runs whatever the deployment built, started or not."""

    async def one_pass() -> None:  # pragma: no cover -- a loop that never ran never calls it
        raise AssertionError

    await TierHealer(one_pass).aclose()
