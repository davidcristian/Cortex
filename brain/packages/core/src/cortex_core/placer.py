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
    ``_placed_gb`` ledger tracks what is placed against it (a resident at or above the cap yields no
    headroom, so every subagent overflows to CPU -- a valid degenerate state, not an error). Both
    values are validated at the composition root (pydantic ``gt``/``ge``), so this stays a trusting
    policy object like ``SingleResidentModelManager``.

    Which resident is charged is not a constant, and that is what ``charge_handoff`` /
    ``charge_standing`` exist for (ADR-0030 handoff-window addendum). A handoff evicts the cortex
    and puts a ~19 GB deep model on the same card, so a fit-test against the cortex's reservation
    during that window describes a machine that does not exist: it credits room the deep model has
    taken and reserves room for a model that has left. The window is written by the residency
    scope, the only thing that knows when the card changed hands.
    """

    def __init__(self, *, soft_cap_gb: float, cortex_reservation_gb: float) -> None:
        self._soft_cap_gb = soft_cap_gb
        self._cortex_reservation_gb = cortex_reservation_gb
        # What the model holding the card costs right now. The cortex outside a handoff, the deep
        # model inside one; a separate field from the reservation above precisely so the standing
        # figure survives the window and can be charged again on the way out.
        self._resident_gb = cortex_reservation_gb
        self._placed_gb = 0.0
        # Whether the tier a GPU placement lands on is believed to be running. Not arithmetic and
        # deliberately not expressed as arithmetic (a resident charged large enough to crowd the
        # cap out would say "no room" where the truth is "no server"), so it is its own bit,
        # written by ``residency_tiers.py`` and read before the headroom is computed at all.
        self._gpu_closed = False

    def place(self, request: PlacementRequest) -> Placement:
        """Reserve on GPU when it fits the headroom, else spill to CPU (reserving nothing).

        Headroom is ``soft_cap - resident - placed``; the boundary is inclusive, so a spawn that
        exactly fills the remaining headroom still lands on GPU. Whole-model only -- never a
        partial GPU+CPU straddle for a 2-4B (verified worst-of-both-worlds, ADR-0012). A closed
        GPU short-circuits all of that: there is nowhere for a GPU placement to run, so the
        headroom is not even consulted and the spawn goes straight to the CPU it would otherwise
        reach only after a failed attempt and a re-run.
        """
        headroom = self._soft_cap_gb - self._resident_gb - self._placed_gb
        if not self._gpu_closed and request.vram_gb <= headroom:
            self._placed_gb += request.vram_gb
            return Placement(target=PlacementTarget.GPU, reserved_gb=request.vram_gb)
        return Placement(target=PlacementTarget.CPU, reserved_gb=0.0)

    def release(self, placement: Placement) -> None:
        """Return the placement's reserved VRAM to the ledger (a no-op for a CPU placement).

        Must pair exactly once with a ``place`` -- ``SubagentRunner`` does so in a ``finally``.
        """
        self._placed_gb -= placement.reserved_gb

    def charge_handoff(self, *, resident_gb: float) -> None:
        """Charge the deep model a handoff swapped in, in place of the cortex it evicted.

        Written by the residency scope at the moment the swap begins, which is before the deep
        model's weights are allocated: charging early is the safe direction, since the load is the
        allocation and a spawn admitted against room that is about to be taken is the exact
        failure this exists to prevent.

        ``resident_gb`` is the deployment's own measured figure for that tier
        (``CORTEX_SWAP_BRAIN_VRAM_MIB``), the same number the swap's fit check compares against
        what the card reports free immediately before the load. So it is not a fresh reading and
        does not pretend to be: it is a declared cost that a real reading has to clear at swap-in
        for the handoff to happen at all, which is what makes it worth charging here, where
        reading the card would put a network call inside a synchronous fit-test.

        The ledger is untouched: spawns already placed keep their reservation across the edge.
        """
        self._resident_gb = resident_gb

    def charge_standing(self) -> None:
        """Charge the cortex again, once the standing residency is genuinely back.

        Idempotent and safe to call when no handoff ever charged anything, which is what the
        residency scope's exit does on every path it can take.
        """
        self._resident_gb = self._cortex_reservation_gb

    def close_gpu(self) -> None:
        """Stop placing on the GPU: the tier a GPU placement lands on is not running.

        Separate from the charge pair on purpose (ADR-0030 tier-outage addendum). A handoff makes
        the card smaller and the arithmetic is the honest way to say so; a tier that would not
        restart makes the card *unreachable* for spawns, which no number about free memory
        expresses. Keeping them apart is also what lets a handoff run its own charge and reversal
        while a tier is down without either edge quietly reopening the GPU.
        """
        self._gpu_closed = True

    def open_gpu(self) -> None:
        """Place on the GPU again, once the standing residency is whole (idempotent)."""
        self._gpu_closed = False
