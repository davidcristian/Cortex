"""The subagent placement port: where one spawn runs, against which residency."""

from typing import Protocol

from cortex_core.placement import Placement, PlacementRequest


class SubagentPlacer(Protocol):
    """Fits a subagent onto the GPU under the VRAM soft cap, or puts it on the CPU."""

    def place(self, request: PlacementRequest) -> Placement: ...

    def release(self, placement: Placement) -> None: ...

    def charge_handoff(self, *, resident_gb: float) -> None: ...

    def charge_standing(self) -> None: ...

    def close_gpu(self) -> None: ...

    def open_gpu(self) -> None: ...
