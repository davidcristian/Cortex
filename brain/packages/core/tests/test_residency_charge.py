import asyncio
from datetime import UTC, datetime

import pytest

from cortex_core import (
    DeviceMemory,
    Placement,
    PlacementRequest,
    PlacementTarget,
    RecordingSleeper,
    ResidencyPlan,
    ResidencyRestoreError,
    ScriptedModelHost,
    SubagentPlacer,
    SwappingModelManager,
    VramBudgetPlacer,
)

_ENDPOINTS = {"cortex": "http://model-host:8080", "brain": "http://model-host:8081"}

# The measured deep tier is 19125 MiB. A 23.0 GiB cap beside an 11.3 GiB cortex reservation
# leaves 11.7 GiB free normally and 4.32 GiB during a handoff, so the 5.5 GiB spawn fits on one
# side of the swap and not the other. These numbers are a scenario, not the shipped defaults.
_DEEP_MIB = 19125
_SPAWN_GB = 5.5
_SOFT_CAP_GB = 23.0
_CORTEX_GB = 11.3
_CARD = DeviceMemory(free_mib=22800, total_mib=24463)


class _FixedClock:
    """A clock that never advances; every deadline here is either generous or already passed."""

    def now(self) -> datetime:
        return datetime(2026, 8, 7, 6, 0, tzinfo=UTC)


def _plan(**overrides: object) -> ResidencyPlan:
    fields: dict[str, object] = {
        "cortex_model": "cortex",
        "brain_model": "brain",
        "coresident": True,
        "brain_vram_mib": _DEEP_MIB,
        "load_timeout_s": 60.0,
    }
    return ResidencyPlan(**(fields | overrides))  # pyright: ignore[reportArgumentType]


def _placer() -> VramBudgetPlacer:
    return VramBudgetPlacer(soft_cap_gb=_SOFT_CAP_GB, cortex_reservation_gb=_CORTEX_GB)


def _manager(
    host: ScriptedModelHost,
    placer: SubagentPlacer | None,
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


def _peer_spawn() -> PlacementRequest:
    return PlacementRequest("peer", vram_gb=_SPAWN_GB, cpus=1.0, memory_gb=2.0)


def _host(**overrides: object) -> ScriptedModelHost:
    fields: dict[str, object] = {"running": ["cortex"], "device_memory": _CARD}
    return ScriptedModelHost(**(fields | overrides))  # pyright: ignore[reportArgumentType]


async def test_a_spawn_inside_the_handoff_is_fit_tested_against_the_deep_model() -> None:
    placer = _placer()
    manager = _manager(_host(), placer)
    assert placer.place(_peer_spawn()).target is PlacementTarget.GPU
    placer.release(Placement(target=PlacementTarget.GPU, reserved_gb=_SPAWN_GB))
    async with manager.swap_scope("brain"):
        assert placer.place(_peer_spawn()) == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


async def test_the_cortex_is_charged_again_once_it_is_genuinely_serving() -> None:
    placer = _placer()
    manager = _manager(_host(), placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_peer_spawn()).target is PlacementTarget.GPU


async def test_the_window_opens_before_the_fit_check_reads_the_card() -> None:
    host = _host(pause_at=[("start", "brain")])
    placer = _placer()
    manager = _manager(host, placer)
    scope = asyncio.create_task(_hold_scope(manager))
    async with asyncio.timeout(5.0):
        await host.reached[("start", "brain")].wait()
    assert placer.place(_peer_spawn()).target is PlacementTarget.CPU
    host.release[("start", "brain")].set()
    await scope


async def test_a_restore_that_gave_up_keeps_charging_the_model_that_may_still_hold_the_card() -> (
    None
):
    placer = _placer()
    manager = _manager(_host(fail={("start", "cortex"): "no such device"}), placer)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope("brain"):
            pass
    assert placer.place(_peer_spawn()).target is PlacementTarget.CPU


async def test_a_deployment_that_declared_no_figure_keeps_the_arithmetic_it_always_had() -> None:
    placer = _placer()
    manager = _manager(_host(), placer, _plan(coresident=False, brain_vram_mib=0))
    async with manager.swap_scope("brain"):
        assert placer.place(_peer_spawn()).target is PlacementTarget.GPU
        oversized = PlacementRequest("peer", vram_gb=12.0, cpus=1.0, memory_gb=2.0)
        assert placer.place(oversized).target is PlacementTarget.CPU


async def test_a_swap_with_no_placer_at_all_still_swaps() -> None:
    host = _host()
    manager = _manager(host, None)
    async with manager.swap_scope("brain"):
        assert "brain" in host.running
    assert "cortex" in host.running


async def test_a_spawn_placed_before_the_window_keeps_its_reservation_across_both_edges() -> None:
    placer = _placer()
    manager = _manager(_host(), placer)
    placed = placer.place(_peer_spawn())
    assert placed.target is PlacementTarget.GPU
    async with manager.swap_scope("brain"):
        pass
    placer.release(placed)
    assert placer.place(PlacementRequest("peer", vram_gb=11.7, cpus=1.0, memory_gb=2.0)).target is (
        PlacementTarget.GPU
    )


async def _hold_scope(manager: SwappingModelManager) -> None:
    """Enter and leave the scope, so a paused swap can be watched from the outside."""
    async with manager.swap_scope("brain"):
        pass
