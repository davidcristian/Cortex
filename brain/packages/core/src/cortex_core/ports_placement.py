"""The subagent placement port: where one spawn runs, against which residency (ADR-0012)."""

from typing import Protocol

from cortex_core.placement import Placement, PlacementRequest


class SubagentPlacer(Protocol):
    """Fit-tests a subagent onto the GPU under the VRAM soft cap, else CPU (ADR-0012)."""

    def place(self, request: PlacementRequest) -> Placement: ...

    def release(self, placement: Placement) -> None: ...

    def charge_handoff(self, *, resident_gb: float) -> None: ...

    def charge_standing(self) -> None: ...
