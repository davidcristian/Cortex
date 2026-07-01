"""Behavior tests for the placement values: target/ngl and the resource-ask guards (ADR-0012)."""

import dataclasses

import pytest

from cortex_core import Placement, PlacementRequest, PlacementTarget


def test_ngl_maps_target_to_the_offload_flag() -> None:
    """GPU means every layer offloaded (-ngl 99); CPU means none (-ngl 0)."""
    assert PlacementTarget.GPU.ngl == 99
    assert PlacementTarget.CPU.ngl == 0


def test_a_valid_request_carries_its_resource_ask() -> None:
    request = PlacementRequest("subagent", vram_gb=2.0, cpus=1.5, memory_gb=3.0)
    assert (request.model, request.vram_gb, request.cpus, request.memory_gb) == (
        "subagent",
        2.0,
        1.5,
        3.0,
    )


@pytest.mark.parametrize(
    ("vram_gb", "cpus", "memory_gb"),
    [
        (0.0, 1.0, 1.0),  # non-positive vram
        (-1.0, 1.0, 1.0),
        (1.0, 0.0, 1.0),  # vram fine, non-positive cpus
        (1.0, 1.0, 0.0),  # vram + cpus fine, non-positive memory
    ],
)
def test_a_nonpositive_resource_ask_is_rejected(
    vram_gb: float, cpus: float, memory_gb: float
) -> None:
    with pytest.raises(ValueError, match="must all be > 0"):
        PlacementRequest("subagent", vram_gb=vram_gb, cpus=cpus, memory_gb=memory_gb)


def test_placement_is_frozen() -> None:
    placement = Placement(target=PlacementTarget.GPU, reserved_gb=2.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        placement.reserved_gb = 3.0  # type: ignore[misc]
