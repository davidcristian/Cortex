"""VramBudgetPlacer: the pure VRAM-budget bookkeeping for subagent placement, with no I/O."""

from cortex_core.placement import Placement, PlacementRequest, PlacementTarget


class VramBudgetPlacer:
    """SubagentPlacer v1: fit each spawn under the VRAM soft cap, and overflow to the CPU."""

    def __init__(self, *, soft_cap_gb: float, cortex_reservation_gb: float) -> None:
        self._soft_cap_gb = soft_cap_gb
        self._cortex_reservation_gb = cortex_reservation_gb
        self._resident_gb = cortex_reservation_gb
        self._placed_gb = 0.0
        # Its own flag rather than arithmetic: a resident charged large enough to use up the
        # cap would report "no room" where the truth is "no server". Written by
        # residency_tiers.py, and read before the headroom is computed at all.
        self._gpu_closed = False

    def place(self, request: PlacementRequest) -> Placement:
        """Reserve on GPU when it fits the headroom, else spill to CPU (reserving nothing)."""
        headroom = self._soft_cap_gb - self._resident_gb - self._placed_gb
        if not self._gpu_closed and request.vram_gb <= headroom:
            self._placed_gb += request.vram_gb
            return Placement(target=PlacementTarget.GPU, reserved_gb=request.vram_gb)
        return Placement(target=PlacementTarget.CPU, reserved_gb=0.0)

    def release(self, placement: Placement) -> None:
        """Return the placement's reserved VRAM to the ledger (a no-op for a CPU placement)."""
        self._placed_gb -= placement.reserved_gb

    def charge_handoff(self, *, resident_gb: float) -> None:
        """Charge the deep model a handoff swapped in, in place of the cortex it evicted."""
        self._resident_gb = resident_gb

    def charge_baseline(self) -> None:
        """Charge the cortex again, once it is genuinely serving."""
        self._resident_gb = self._cortex_reservation_gb

    def close_gpu(self) -> None:
        """Stop placing on the GPU: the tier a GPU placement would run on is not running."""
        self._gpu_closed = True

    def open_gpu(self) -> None:
        """Place on the GPU again, once every tier is serving (idempotent)."""
        self._gpu_closed = False
