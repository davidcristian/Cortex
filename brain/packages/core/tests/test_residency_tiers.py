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
    PlainFormatter,
    RecordingSleeper,
    ResidencyPlan,
    ScriptedModelHost,
    StandingTiers,
    SwappingModelManager,
    TierFault,
    TierHealer,
    VramBudgetPlacer,
    converge_residency,
    sweep_tiers,
)

_ENDPOINTS = {"cortex": "http://llama-cortex:8080", "brain": "http://llama-brain:8081"}
_TIER = "subagent-gpu"
_OTHER_TIER = "subagent-gpu-2"
_GHOST = "tier-with-no-artifact"
_RETRY_LOGGER = "cortex_core.residency_sweep"
_LOOP_NAME = "residency-tier-healer"


def _open() -> bool:
    """An event that is never set, for cases that run one pass rather than the manager."""
    return True


def _retry_log(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Only the retry loop's own lines, since a case that swapped first also logged that."""
    return [record.msg for record in caplog.records if record.name == _RETRY_LOGGER]


def _retry_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The same lines as an operator sees them, through the formatter the entry point installs."""
    return [
        PlainFormatter().format(record) for record in caplog.records if record.name == _RETRY_LOGGER
    ]


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
    """3.0 GiB of headroom beside the cortex, so the 2.0 GiB subagent below fits the GPU."""
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
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, placer)
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    # Released, or the second request below would overflow for want of headroom instead of
    # because GPU placement was closed.
    placer.release(before)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_peer_that_came_back_leaves_placement_where_it_found_it() -> None:
    placer = _placer()
    manager = _manager(ScriptedModelHost(running=["cortex", _TIER]), placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert manager.residency() == RESIDENCY_SERVING


async def test_the_seam_says_which_peer_is_down_while_the_cortex_serves() -> None:
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    report = manager.residency()
    assert report.serving is True
    assert report.detail == TIERS_MISSING_DETAIL.format(models=_TIER)


async def test_an_evicted_tier_is_not_a_missing_one() -> None:
    host = ScriptedModelHost(running=["cortex", _TIER], fail={("start", _TIER): "no such device"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    assert manager.residency().detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    async with manager.swap_scope("brain"):
        assert manager.residency() == RESIDENCY_DEEP


async def test_a_second_handoff_that_restarts_the_peer_reopens_the_gpu() -> None:
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
    tiers = StandingTiers()
    assert tiers.placer is None
    tiers.mark_missing(_TIER)
    assert tiers.missing == (_TIER,)
    assert tiers.note_on(RESIDENCY_SERVING).detail == TIERS_MISSING_DETAIL.format(models=_TIER)
    tiers.mark_unhosted(_GHOST)
    assert tiers.missing == (_TIER, _GHOST)
    assert tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    tiers.mark_standing(_TIER)
    tiers.mark_standing(_GHOST)
    assert tiers.note_on(RESIDENCY_SERVING) == RESIDENCY_SERVING


async def test_a_sweep_that_meets_the_fence_mid_pass_records_without_starting() -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex"])
    tiers = StandingTiers(placer)
    await sweep_tiers(host, _plan(), tiers, lambda: False)
    assert host.calls == [("status", _TIER)]
    assert tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_start_the_host_refuses_leaves_the_tier_recorded_and_the_pass_alive(
    caplog: pytest.LogCaptureFixture,
) -> None:
    host = ScriptedModelHost(running=["cortex"], fail={("start", _TIER): "no such device"})
    tiers = StandingTiers(_placer())
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await sweep_tiers(host, _plan(evict_models=(_TIER, _OTHER_TIER)), tiers, _open)
    assert host.calls == [
        ("status", _TIER),
        ("start", _TIER),
        ("status", _OTHER_TIER),
        ("start", _OTHER_TIER),
    ]
    assert tiers.missing == (_TIER, _OTHER_TIER)
    assert (
        f"WARNING:{_RETRY_LOGGER}:a tier of the standing residency could not be started"
        f' error="no such device" model={_TIER}'
    ) in _retry_lines(caplog)


def test_marking_a_tier_standing_that_was_never_missing_changes_nothing() -> None:
    placer = _placer()
    tiers = StandingTiers(placer)
    tiers.mark_standing(_TIER)
    assert tiers.missing == ()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_retry_that_finds_the_tier_serving_reopens_the_gpu(
    caplog: pytest.LogCaptureFixture,
) -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("start", _TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    with caplog.at_level(logging.INFO, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU
    assert _retry_log(caplog) == ["a tier the standing residency was missing is serving again"]


async def test_a_sweep_leaves_a_tier_that_is_still_loading_alone() -> None:
    host = ScriptedModelHost(running=[_TIER], status_override={_TIER: ModelHostState.LOADING})
    tiers = StandingTiers(_placer())
    tiers.mark_missing(_TIER)
    await sweep_tiers(host, _plan(), tiers, _open)
    assert host.calls == [("status", _TIER)]
    assert tiers.missing == (_TIER,)


async def test_a_sweep_that_cannot_reach_the_host_leaves_the_record_alone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    placer = _placer()
    host = ScriptedModelHost(
        running=["cortex", _TIER],
        fail={("start", _TIER): "no such device", ("status", _TIER): "connection refused"},
    )
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert _retry_lines(caplog) == [
        f"WARNING:{_RETRY_LOGGER}:a tier of the standing residency could not be asked about"
        f' error="connection refused" model={_TIER}'
    ]
    standing = StandingTiers(_placer())
    await sweep_tiers(host, _plan(), standing, _open)
    assert standing.missing == ()


async def test_a_sweep_defers_while_a_handoff_owns_the_gpu() -> None:
    host = ScriptedModelHost(running=["cortex", _TIER], fail_once={("start", _TIER): "device busy"})
    manager = _manager(host, _placer())
    async with manager.swap_scope("brain"):
        pass
    async with manager.swap_scope("brain"):
        host.calls.clear()
        await manager.heal_residency()
        assert host.calls == []


async def test_a_sweep_defers_while_a_handoff_is_claimed_and_the_pool_is_draining() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _placer())
    async with manager.handoff_claim():
        host.calls.clear()
        await manager.heal_residency()
        assert host.calls == []
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("start", _TIER)]


async def test_a_peer_that_accepted_its_start_and_then_died_is_found_by_the_next_pass() -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER])
    manager = _manager(host, placer)
    async with manager.swap_scope("brain"):
        pass
    host.set_status(_TIER, ModelHostState.FAILED)
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    await manager.heal_residency()
    assert manager.standing_tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert manager.residency().detail == TIERS_MISSING_DETAIL.format(models=_TIER)


async def test_a_peer_that_died_between_handoffs_is_found_without_any_handoff(
    caplog: pytest.LogCaptureFixture,
) -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER])
    manager = _manager(host, placer)
    host.set_status(_TIER, ModelHostState.FAILED)
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    with caplog.at_level(logging.WARNING, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    assert _retry_lines(caplog) == [
        f"WARNING:{_RETRY_LOGGER}:a tier of the standing residency stopped without anything "
        f"asking it to; delegated work runs on the CPU until it is serving again "
        f"model={_TIER} state=failed"
    ]


async def test_a_peer_nothing_ever_started_is_found_by_the_first_pass() -> None:
    placer = _placer()
    host = ScriptedModelHost(
        running=["cortex", "brain"], fail={("stop", "brain"): "still resident"}
    )
    manager = _manager(host, placer)
    settled = await converge_residency(
        host, _plan(), manager.standing_tiers, clock=_FixedClock(), sleeper=RecordingSleeper()
    )
    assert settled is False
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    await manager.heal_residency()
    assert manager.standing_tiers.missing == (_TIER,)
    assert placer.place(_spawn()).target is PlacementTarget.CPU


async def test_a_boot_that_could_not_reach_the_host_is_swept_when_it_answers_again() -> None:
    placer = _placer()
    host = ScriptedModelHost(running=[], fail_once={("status", "brain"): "connection refused"})
    manager = _manager(host, placer)
    settled = await converge_residency(
        host, _plan(), manager.standing_tiers, clock=_FixedClock(), sleeper=RecordingSleeper()
    )
    assert settled is False
    assert manager.standing_tiers.missing == ()
    before = placer.place(_spawn())
    assert before.target is PlacementTarget.GPU
    placer.release(before)
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("start", _TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    await manager.heal_residency()
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_tier_the_roster_never_had_is_recorded_once_and_never_asked_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST])
    plan = _plan(evict_models=(_GHOST,))
    manager = _manager(host, placer, plan)
    with caplog.at_level(logging.ERROR, logger=_RETRY_LOGGER):
        await manager.heal_residency()
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    assert placer.place(_spawn()).target is PlacementTarget.CPU
    host.calls.clear()
    await manager.heal_residency()
    await manager.heal_residency()
    assert host.calls == []
    (line,) = _retry_lines(caplog)
    assert f"model={_GHOST}" in line
    assert "CORTEX_SWAP_EVICT_MODELS" in line


async def test_a_restart_refused_for_a_tier_the_roster_lacks_is_not_an_ordinary_refusal() -> None:
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST])
    manager = _manager(host, _placer(), _plan(evict_models=(_GHOST,)))
    settled = await converge_residency(
        host,
        _plan(evict_models=(_GHOST,)),
        manager.standing_tiers,
        clock=_FixedClock(),
        sleeper=RecordingSleeper(),
    )
    assert settled is True
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED


async def test_a_replaced_daemon_asks_an_unhosted_tier_again() -> None:
    host = ScriptedModelHost(running=["cortex"], unhosted=[_GHOST], boot_id="first")
    plan = _plan(evict_models=(_GHOST,))
    manager = _manager(host, _placer(), plan)
    await manager.heal_residency()
    assert manager.standing_tiers.fault_of(_GHOST) is TierFault.UNHOSTED
    host.unhosted.clear()
    host.boot = "second"
    async with manager.swap_scope("brain"):
        pass
    assert manager.standing_tiers.missing == ()


async def test_a_pass_that_finds_every_tier_serving_writes_nothing_and_starts_nothing() -> None:
    placer = _placer()
    host = ScriptedModelHost(running=["cortex", _TIER, _OTHER_TIER])
    manager = _manager(host, placer, _plan(evict_models=(_TIER, _OTHER_TIER)))
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == [("status", _TIER), ("status", _OTHER_TIER)]
    assert placer.place(_spawn()).target is PlacementTarget.GPU


async def test_a_deployment_that_evicts_nothing_still_asks_nobody_anything() -> None:
    host = ScriptedModelHost(running=["cortex"])
    manager = _manager(host, _placer(), _plan(evict_models=()))
    host.calls.clear()
    await manager.heal_residency()
    assert host.calls == []


async def test_the_loop_keeps_retrying_until_it_is_closed() -> None:
    passes = asyncio.Event()
    count = 0

    async def one_pass() -> None:
        nonlocal count
        count += 1
        if count >= 2:
            passes.set()

    healer = TierHealer(one_pass, interval_s=0.001)
    healer.start()
    healer.start()
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
    entered = asyncio.Event()

    async def one_pass() -> None:
        entered.set()

    healer = TierHealer(one_pass, interval_s=3600.0)
    healer.start()
    async with asyncio.timeout(5.0):
        await entered.wait()
        await healer.aclose()


async def test_closing_a_loop_that_never_started_is_a_no_op() -> None:
    async def one_pass() -> None:  # pragma: no cover -- a loop that never ran never calls it
        raise AssertionError

    await TierHealer(one_pass).aclose()
