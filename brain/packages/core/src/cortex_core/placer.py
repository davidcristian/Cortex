"""VramBudgetPlacer: the pure VRAM-budget accountant for subagent placement (no I/O -- ADR-0012).

Owns policy, not a GPU: a live ledger of subagent VRAM placed right now, fit-tested against the
soft cap (``CORTEX_VRAM_SOFT_CAP_GB``) minus the resident cortex's reservation. Each spawn lands
whole-model on GPU (``-ngl 99``) when it fits the headroom, else CPU-only (``-ngl 0``) -- never a
partial straddle. ``place``/``release`` are synchronous and lock-free: with no ``await`` inside, a
coroutine's read-modify-write of the ledger runs to completion without interleaving (single-threaded
asyncio atomicity), so the concurrent batch spawns (``asyncio.gather``, ADR-0010) race the headroom
correctly with no lock. Doing no I/O, it is a pure reference impl of the ``SubagentPlacer`` port,
lives in the core, and is fully covered without a GPU (ADR-0012). The ledger is live-resource state,
never durable state (the one hard rule): rebuilt from zero on construction and freed by a swap,
exactly as it should be, since evicted VRAM is gone.
"""

from cortex_core.placement import Placement, PlacementRequest, PlacementTarget


class VramBudgetPlacer:
    """SubagentPlacer v1: GPU-first fit-test against the VRAM soft cap, CPU overflow (ADR-0012).

    ``soft_cap_gb`` is the policy budget (not free VRAM); ``cortex_reservation_gb`` is the resident
    cortex's measured footprint. Their difference is the whole subagent GPU allowance, and the live
    ``_placed_gb`` ledger tracks what is placed against it (a cortex at or above the cap yields no
    headroom, so every subagent overflows to CPU -- a valid degenerate state, not an error). Both
    values are validated at the composition root (pydantic ``gt``/``ge``), so this stays a trusting
    policy object like ``SingleResidentModelManager``.
    """

    def __init__(self, *, soft_cap_gb: float, cortex_reservation_gb: float) -> None:
        self._soft_cap_gb = soft_cap_gb
        self._cortex_reservation_gb = cortex_reservation_gb
        self._placed_gb = 0.0

    def place(self, request: PlacementRequest) -> Placement:
        """Reserve on GPU when it fits the headroom, else spill to CPU (reserving nothing).

        Headroom is ``soft_cap - cortex_reservation - placed``; the boundary is inclusive, so a
        spawn that exactly fills the remaining headroom still lands on GPU. Whole-model only --
        never a partial GPU+CPU straddle for a 2-4B (verified worst-of-both-worlds, ADR-0012).
        """
        headroom = self._soft_cap_gb - self._cortex_reservation_gb - self._placed_gb
        if request.vram_gb <= headroom:
            self._placed_gb += request.vram_gb
            return Placement(target=PlacementTarget.GPU, reserved_gb=request.vram_gb)
        return Placement(target=PlacementTarget.CPU, reserved_gb=0.0)

    def release(self, placement: Placement) -> None:
        """Return the placement's reserved VRAM to the ledger (a no-op for a CPU placement).

        Must pair exactly once with a ``place`` -- ``SubagentRunner`` does so in a ``finally``.
        """
        self._placed_gb -= placement.reserved_gb
