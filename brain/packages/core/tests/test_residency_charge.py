"""The handoff window as the subagent placer sees it: who is charged while the deep model runs.

The unit under test is the pair of edges the residency scope writes (``residency_charge.py``)
together with the arithmetic they move (``placer.py``), because neither is worth anything alone:
a charge nobody writes is dead code, and a write into a ledger nothing fit-tests against is a
number in a field. So every case here drives the real ``SwappingModelManager`` over the scripted
host and asks the real ``VramBudgetPlacer`` where a spawn would land at that instant.

The numbers are this machine's, measured 2026-08-07 and recorded in ADR-0030's co-residency
addendum: a 24 GB card, a deep tier costing 19125 MiB, an E4B peer tier costing 2878 MiB. They
are used rather than round stand-ins so a reader can check the assertions against the table.

Distrust-green proofs (each mutation applied to production code alone, the core suite re-run,
then reverted):
- deleting ``charge_handoff``'s call in ``residency._swap_in`` reddens
  ``test_a_spawn_inside_the_handoff_is_fit_tested_against_the_deep_model`` and
  ``test_the_window_opens_before_the_fit_check_reads_the_card``;
- deleting ``charge_standing``'s call after the restore reddens
  ``test_the_cortex_is_charged_again_once_it_is_genuinely_serving``;
- hoisting that call out of the ``if`` (so a give-up also restores the standing charge) reddens
  ``test_a_restore_that_gave_up_keeps_charging_the_model_that_may_still_hold_the_card``;
- dropping ``residency_charge``'s ``brain_vram_mib > 0`` guard reddens
  ``test_a_deployment_that_declared_no_figure_keeps_the_arithmetic_it_always_had``;
- charging in ``place`` from ``_cortex_reservation_gb`` instead of ``_resident_gb`` reddens the
  first two cases above.
"""

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

# The card and the deep tier as measured (ADR-0030 co-residency addendum), with a budget chosen so
# one spawn straddles the handoff window: it fits beside the cortex and not beside the deep model,
# which is the flip under test. The three budget numbers are a scenario, not the shipped defaults
# (the shipped ask is 3.5 GiB and the shipped reservation 8.6 since they were measured, and a
# scenario built from those would want its own cap to keep the straddle); 23.0 GiB of a 23.89 GiB
# card leaves 11.7 GiB of standing headroom beside an 11.3 GiB reservation, and 4.32 during a
# handoff, so a 5.5 GiB ask lands on either side of the edge.
_DEEP_MIB = 19125
_SPAWN_GB = 5.5
_SOFT_CAP_GB = 23.0
_CORTEX_GB = 11.3
_CARD = DeviceMemory(free_mib=22800, total_mib=24463)


class _FixedClock:
    """A clock that never advances; every bound here is either generous or already expired."""

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
    """The whole point: the same spawn, the same placer, opposite answers either side of a swap.

    Outside the window this scenario's 5.5 GiB ask fits the 11.7 GiB the cap leaves beside the
    cortex (the module header says why these are a scenario rather than the defaults). Inside
    it the card really holds the deep model's 19125 MiB and about 908 MiB is free, so admitting
    that spawn onto the GPU would be admitting it into memory the deep model already took. It is a
    co-resident handoff, so nothing drained the pool and the spawn genuinely arrives here.
    """
    placer = _placer()
    manager = _manager(_host(), placer)
    assert placer.place(_peer_spawn()).target is PlacementTarget.GPU
    placer.release(Placement(target=PlacementTarget.GPU, reserved_gb=_SPAWN_GB))
    async with manager.swap_scope("brain"):
        assert placer.place(_peer_spawn()) == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


async def test_the_cortex_is_charged_again_once_it_is_genuinely_serving() -> None:
    """The reversal, and it is not a flag flip: the standing figure has to come back exactly."""
    placer = _placer()
    manager = _manager(_host(), placer)
    async with manager.swap_scope("brain"):
        pass
    assert placer.place(_peer_spawn()).target is PlacementTarget.GPU


async def test_the_window_opens_before_the_fit_check_reads_the_card() -> None:
    """Ordering, against the one hazard the fit check cannot see on its own.

    The check reads free memory between the last eviction and the load, and the load takes
    seconds to minutes. A spawn admitted to the GPU in that gap would spend exactly the room the
    check just measured, so the charge is in force while the reading is taken: the swap is paused
    at its ``start`` boundary here, which is after the check answered and before anything is
    allocated, and the placer must already be refusing.
    """
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
    """The safe direction on the one path where nobody knows what is resident.

    The restore ran out of attempts, so the cortex is not serving and the deep model may or may
    not still be on the card. Crediting the cortex's reservation back here would admit GPU work
    against a machine nothing can describe; keeping the handoff's charge sends those spawns to the
    CPU, which is slower and true.
    """
    placer = _placer()
    manager = _manager(_host(fail={("start", "cortex"): "no such device"}), placer)
    with pytest.raises(ResidencyRestoreError):
        async with manager.swap_scope("brain"):
            pass
    assert placer.place(_peer_spawn()).target is PlacementTarget.CPU


async def test_a_deployment_that_declared_no_figure_keeps_the_arithmetic_it_always_had() -> None:
    """No declared cost is not a licence to charge nothing: that would credit the evicted cortex.

    ``brain_vram_mib`` is zero on the shipped defaults, and there is then no honest number for the
    deep model, so the window is not entered at all and the placer answers exactly as it did
    before any of this existed. Asserted with an ask that only a **credited** cortex could fit
    (12.0 GiB against 11.7 GiB of standing headroom), because charging a declared zero would hand
    the whole soft cap to the pool, which is the opposite failure and the reason for the guard.
    """
    placer = _placer()
    manager = _manager(_host(), placer, _plan(coresident=False, brain_vram_mib=0))
    async with manager.swap_scope("brain"):
        assert placer.place(_peer_spawn()).target is PlacementTarget.GPU
        oversized = PlacementRequest("peer", vram_gb=12.0, cpus=1.0, memory_gb=2.0)
        assert placer.place(oversized).target is PlacementTarget.CPU


async def test_a_swap_with_no_placer_at_all_still_swaps() -> None:
    """A deployment with no subagent pool: the edges are written to nobody and nothing breaks."""
    host = _host()
    manager = _manager(host, None)
    async with manager.swap_scope("brain"):
        assert "brain" in host.running
    assert "cortex" in host.running


async def test_a_spawn_placed_before_the_window_keeps_its_reservation_across_both_edges() -> None:
    """The ledger is not the resident: a running spawn's VRAM did not move when the card did.

    Charging the window must not double-count or forget what is already placed, or the release
    that follows the spawn would credit the budget an amount it never debited.
    """
    placer = _placer()
    manager = _manager(_host(), placer)
    placed = placer.place(_peer_spawn())
    assert placed.target is PlacementTarget.GPU
    async with manager.swap_scope("brain"):
        pass
    placer.release(placed)
    # Back to a full standing headroom: 23.0 - 11.3 leaves room for the peer and then some.
    assert placer.place(PlacementRequest("peer", vram_gb=11.7, cpus=1.0, memory_gb=2.0)).target is (
        PlacementTarget.GPU
    )


async def _hold_scope(manager: SwappingModelManager) -> None:
    """Enter and leave the scope, so a paused swap can be observed from the outside."""
    async with manager.swap_scope("brain"):
        pass
