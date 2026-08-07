"""VramBudgetPlacer: the pure VRAM-budget accountant for subagent placement (no I/O -- ADR-0012)."""

from cortex_core.placement import Placement, PlacementRequest, PlacementTarget


class VramBudgetPlacer:
    """SubagentPlacer v1: GPU-first fit-test against the VRAM soft cap, CPU overflow (ADR-0012)."""

    def __init__(self, *, soft_cap_gb: float, cortex_reservation_gb: float) -> None:
        self._soft_cap_gb = soft_cap_gb
        self._cortex_reservation_gb = cortex_reservation_gb
        # What the model holding the card costs right now. The cortex outside a handoff, the deep
        # model inside one; a separate field from the reservation above precisely so the standing
        # figure survives the window and can be charged again on the way out.
        self._resident_gb = cortex_reservation_gb
        self._placed_gb = 0.0

    def place(self, request: PlacementRequest) -> Placement:
        """Reserve on GPU when it fits the headroom, else spill to CPU (reserving nothing)."""
        headroom = self._soft_cap_gb - self._resident_gb - self._placed_gb
        if request.vram_gb <= headroom:
            self._placed_gb += request.vram_gb
            return Placement(target=PlacementTarget.GPU, reserved_gb=request.vram_gb)
        return Placement(target=PlacementTarget.CPU, reserved_gb=0.0)

    def release(self, placement: Placement) -> None:
        """Return the placement's reserved VRAM to the ledger (a no-op for a CPU placement).

        Must pair exactly once with a ``place`` -- ``SubagentRunner`` does so in a ``finally``.
        """
        self._placed_gb -= placement.reserved_gb

    def charge_handoff(self, *, resident_gb: float) -> None:
        """Charge the deep model a handoff swapped in, in place of the cortex it evicted."""
        self._resident_gb = resident_gb

    def charge_standing(self) -> None:
        """Charge the cortex again, once the standing residency is genuinely back.

        Idempotent and safe to call when no handoff ever charged anything, which is what the
        residency scope's exit does on every path it can take.
        """
        self._resident_gb = self._cortex_reservation_gb
