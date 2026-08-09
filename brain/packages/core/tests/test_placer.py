"""Behavior tests for VramBudgetPlacer: the GPU-first fit-test + VRAM ledger (ADR-0012).

These pin the SubagentPlacer contract: Slice 11's process-lifecycle adapter must pass the same
checks against the same port. Headroom = soft_cap - cortex_reservation - placed.

The port's other two verbs, ``close_gpu``/``open_gpu``, are pinned here and exercised end to end
in the core's test_residency_tiers.py, where the residency scope is what writes them.
Distrust-green: consulting the headroom before the closed flag in ``place`` reddens 7 across the
workspace, two of them here.
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


def test_charging_a_handoff_fit_tests_against_the_deep_model_instead_of_the_cortex() -> None:
    """The window's arithmetic: the resident term names what actually holds the card."""
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)  # headroom 11.7
    assert placer.place(_request(2.81)).target is PlacementTarget.GPU
    placer.release(Placement(target=PlacementTarget.GPU, reserved_gb=2.81))
    placer.charge_handoff(resident_gb=18.68)  # the measured 19125 MiB deep tier
    # 23.0 - 18.68 = 4.32 left, which is the ~0.9 GB the card really had free beside the peer
    # once the arithmetic stops crediting an evicted cortex; a second peer no longer fits.
    assert placer.place(_request(2.81)).target is PlacementTarget.GPU
    assert placer.place(_request(2.81)).target is PlacementTarget.CPU


def test_charging_the_standing_residency_restores_the_cortex_s_own_reservation() -> None:
    """The reversal puts back the constructor's figure, not the last thing charged."""
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placer.charge_handoff(resident_gb=18.68)
    assert placer.place(_request(9.0)).target is PlacementTarget.CPU
    placer.charge_standing()
    assert placer.place(_request(9.0)).target is PlacementTarget.GPU


def test_charging_the_standing_residency_with_no_handoff_first_changes_nothing() -> None:
    """Idempotent, because the residency scope's exit owes it on every path it can take."""
    placer = _placer()  # headroom 3.0
    placer.charge_standing()
    placer.charge_standing()
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_a_handoff_charge_does_not_disturb_what_is_already_placed() -> None:
    """A spawn's VRAM did not move because the card changed hands, so its ledger entry stands."""
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placed = placer.place(_request(4.0))
    placer.charge_handoff(resident_gb=18.0)
    placer.charge_standing()
    placer.release(placed)  # credits exactly the 4.0 it debited, no more
    assert placer.place(_request(11.7)).target is PlacementTarget.GPU
    assert placer.place(_request(0.1)).target is PlacementTarget.CPU


def test_a_closed_gpu_sends_a_fitting_spawn_to_the_cpu() -> None:
    """Room is not the question a closed GPU answers: there is nowhere for the spawn to run.

    The ask here fits the headroom with 1.0 GiB to spare, so nothing about the arithmetic sends
    it to the CPU. What does is the tier a GPU placement lands on not being up
    (``residency_tiers.py``).
    """
    placer = _placer()  # headroom 3.0
    placer.close_gpu()
    assert placer.place(_request(2.0)) == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


def test_opening_the_gpu_again_restores_the_fit_test_unchanged() -> None:
    """Both verbs are idempotent, and neither of them is a number."""
    placer = _placer()  # headroom 3.0
    placer.close_gpu()
    placer.close_gpu()
    placer.open_gpu()
    placer.open_gpu()
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_closing_the_gpu_leaves_the_ledger_exactly_as_it_found_it() -> None:
    """A spawn placed before the close still holds its reservation and still releases it."""
    placer = _placer()  # headroom 3.0
    placed = placer.place(_request(3.0))
    placer.close_gpu()
    placer.open_gpu()
    assert placer.place(_request(0.1)).target is PlacementTarget.CPU  # the 3.0 is still debited
    placer.release(placed)
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_a_handoff_charge_does_not_reopen_a_closed_gpu() -> None:
    """The two pairs are independent: a swap heals its own charge and never a tier's outage."""
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placer.close_gpu()
    placer.charge_handoff(resident_gb=18.0)
    placer.charge_standing()
    assert placer.place(_request(1.0)).target is PlacementTarget.CPU
