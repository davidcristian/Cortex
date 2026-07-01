"""Behavior tests for VramBudgetPlacer: the GPU-first fit-test + VRAM ledger (ADR-0012).

These pin the SubagentPlacer contract: Slice 11's process-lifecycle adapter must pass the same
checks against the same port. Headroom = soft_cap - cortex_reservation - placed.
"""

from cortex_core import (
    Placement,
    PlacementRequest,
    PlacementTarget,
    SubagentPlacer,
    VramBudgetPlacer,
)


def _placer(soft_cap_gb: float = 14.0, cortex_reservation_gb: float = 11.0) -> VramBudgetPlacer:
    return VramBudgetPlacer(soft_cap_gb=soft_cap_gb, cortex_reservation_gb=cortex_reservation_gb)


def _request(vram_gb: float) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=vram_gb, cpus=1.0, memory_gb=1.0)


def test_placer_satisfies_the_port() -> None:
    """The concrete placer is a structural SubagentPlacer (pins the port signature)."""
    placer: SubagentPlacer = _placer()
    assert isinstance(placer, VramBudgetPlacer)


def test_a_subagent_that_fits_lands_on_gpu() -> None:
    # headroom = 14 - 11 = 3.0; a 2 GB subagent fits.
    placement = _placer().place(_request(2.0))
    assert placement == Placement(target=PlacementTarget.GPU, reserved_gb=2.0)


def test_exactly_filling_the_headroom_still_lands_on_gpu_then_the_next_spills() -> None:
    placer = _placer()  # headroom 3.0
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU  # 3.0 <= 3.0 (inclusive)
    # headroom is now 0.0; the smallest further ask overflows to CPU (0.1 > 0.0).
    spill = placer.place(_request(0.1))
    assert spill == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


def test_a_second_subagent_overflows_to_cpu_when_headroom_is_exhausted() -> None:
    placer = _placer()  # headroom 3.0
    assert placer.place(_request(2.0)).target is PlacementTarget.GPU  # headroom 3.0 → 1.0
    assert placer.place(_request(2.0)).target is PlacementTarget.CPU  # 2.0 > 1.0 → CPU


def test_releasing_a_gpu_placement_frees_the_headroom_again() -> None:
    placer = _placer()  # headroom 3.0
    first = placer.place(_request(3.0))  # fills the GPU
    assert placer.place(_request(3.0)).target is PlacementTarget.CPU  # no headroom left
    placer.release(first)  # give the 3 GB back
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU  # fits again


def test_releasing_a_cpu_placement_is_a_no_op() -> None:
    placer = _placer()  # headroom 3.0
    cpu = placer.place(_request(5.0))  # 5 > 3 → CPU, reserved nothing
    assert cpu.reserved_gb == 0.0
    placer.release(cpu)  # frees nothing
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU  # full headroom intact


def test_a_cortex_at_the_cap_leaves_no_gpu_headroom() -> None:
    placer = _placer(soft_cap_gb=11.0, cortex_reservation_gb=11.0)  # headroom 0.0
    assert placer.place(_request(1.0)).target is PlacementTarget.CPU
