from cortex_core import (
    Placement,
    PlacementRequest,
    PlacementTarget,
    SubagentPlacer,
    VramBudgetPlacer,
)


def _placer(soft_cap_gb: float = 14.0, cortex_reservation_gb: float = 11.0) -> VramBudgetPlacer:
    # The defaults leave 3.0 GiB of headroom, which is what the tests below place against.
    return VramBudgetPlacer(soft_cap_gb=soft_cap_gb, cortex_reservation_gb=cortex_reservation_gb)


def _request(vram_gb: float) -> PlacementRequest:
    return PlacementRequest("subagent", vram_gb=vram_gb, cpus=1.0, memory_gb=1.0)


def test_placer_satisfies_the_port() -> None:
    placer: SubagentPlacer = _placer()
    assert isinstance(placer, VramBudgetPlacer)


def test_a_subagent_that_fits_lands_on_gpu() -> None:
    placement = _placer().place(_request(2.0))
    assert placement == Placement(target=PlacementTarget.GPU, reserved_gb=2.0)


def test_exactly_filling_the_headroom_still_lands_on_gpu_then_the_next_spills() -> None:
    placer = _placer()
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU
    spill = placer.place(_request(0.1))
    assert spill == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


def test_a_second_subagent_overflows_to_cpu_when_headroom_is_exhausted() -> None:
    placer = _placer()
    assert placer.place(_request(2.0)).target is PlacementTarget.GPU
    assert placer.place(_request(2.0)).target is PlacementTarget.CPU


def test_releasing_a_gpu_placement_frees_the_headroom_again() -> None:
    placer = _placer()
    first = placer.place(_request(3.0))
    assert placer.place(_request(3.0)).target is PlacementTarget.CPU
    placer.release(first)
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_releasing_a_cpu_placement_is_a_no_op() -> None:
    placer = _placer()
    cpu = placer.place(_request(5.0))
    assert cpu.reserved_gb == 0.0
    placer.release(cpu)
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_a_cortex_at_the_cap_leaves_no_gpu_headroom() -> None:
    placer = _placer(soft_cap_gb=11.0, cortex_reservation_gb=11.0)
    assert placer.place(_request(1.0)).target is PlacementTarget.CPU


def test_charging_a_handoff_fit_tests_against_the_deep_model_instead_of_the_cortex() -> None:
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    assert placer.place(_request(2.81)).target is PlacementTarget.GPU
    placer.release(Placement(target=PlacementTarget.GPU, reserved_gb=2.81))
    # 18.68 GiB is the measured 19125 MiB deep tier, so 23.0 - 18.68 leaves 4.32 GiB: one more
    # 2.81 GiB subagent fits beside it and a second does not.
    placer.charge_handoff(resident_gb=18.68)
    assert placer.place(_request(2.81)).target is PlacementTarget.GPU
    assert placer.place(_request(2.81)).target is PlacementTarget.CPU


def test_charging_the_standing_residency_restores_the_cortex_s_own_reservation() -> None:
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placer.charge_handoff(resident_gb=18.68)
    assert placer.place(_request(9.0)).target is PlacementTarget.CPU
    placer.charge_standing()
    assert placer.place(_request(9.0)).target is PlacementTarget.GPU


def test_charging_the_standing_residency_with_no_handoff_first_changes_nothing() -> None:
    placer = _placer()
    placer.charge_standing()
    placer.charge_standing()
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_a_handoff_charge_does_not_disturb_what_is_already_placed() -> None:
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placed = placer.place(_request(4.0))
    placer.charge_handoff(resident_gb=18.0)
    placer.charge_standing()
    placer.release(placed)
    assert placer.place(_request(11.7)).target is PlacementTarget.GPU
    assert placer.place(_request(0.1)).target is PlacementTarget.CPU


def test_a_closed_gpu_sends_a_fitting_spawn_to_the_cpu() -> None:
    placer = _placer()
    placer.close_gpu()
    assert placer.place(_request(2.0)) == Placement(target=PlacementTarget.CPU, reserved_gb=0.0)


def test_opening_the_gpu_again_restores_the_fit_test_unchanged() -> None:
    placer = _placer()
    placer.close_gpu()
    placer.close_gpu()
    placer.open_gpu()
    placer.open_gpu()
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_closing_the_gpu_leaves_the_ledger_exactly_as_it_found_it() -> None:
    placer = _placer()
    placed = placer.place(_request(3.0))
    placer.close_gpu()
    placer.open_gpu()
    assert placer.place(_request(0.1)).target is PlacementTarget.CPU
    placer.release(placed)
    assert placer.place(_request(3.0)).target is PlacementTarget.GPU


def test_a_handoff_charge_does_not_reopen_a_closed_gpu() -> None:
    placer = _placer(soft_cap_gb=23.0, cortex_reservation_gb=11.3)
    placer.close_gpu()
    placer.charge_handoff(resident_gb=18.0)
    placer.charge_standing()
    assert placer.place(_request(1.0)).target is PlacementTarget.CPU
