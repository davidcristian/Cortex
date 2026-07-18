"""What the GPU is serving right now, in the words the seam shows a human (ADR-0030 d6)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResidencyReport:
    """One answer about the GPU: is the usual assistant serving, and if not, what is happening."""

    serving: bool
    detail: str


# The standing residency: the cortex is up and turns run normally. A fresh manager seeds this
# too, and the seed is only ever an assumption, so boot convergence republishes it (or does not)
# from what it actually observed, before the seam serves anything.
RESIDENCY_SERVING = ResidencyReport(serving=True, detail="")

# The swap in, from the moment the lease is taken to the moment the deep model gates ready. It
# covers the eviction as well as the load, because nothing is serving for either.
RESIDENCY_LOADING = ResidencyReport(
    serving=False, detail="swapping to the deep model; this takes a few minutes"
)

# The deep model is resident and answering the handoff. The brain is up and busy, and the usual
# assistant is unloaded, so a turn started now would wait for the swap back.
RESIDENCY_DEEP = ResidencyReport(serving=False, detail="a deep task is in progress")

# The swap back, which is the recovery path: the deep model is stopped and the cortex is loading.
RESIDENCY_RESTORING = ResidencyReport(serving=False, detail="bringing the usual assistant back")

# The one state no retry cleared: the restore gave up loudly and the GPU serves nothing. It
# stands until the brain restarts and boot recovery converges residency again, which is what
# docs/runbooks/model-swap.md's manual recovery ends with.
RESIDENCY_LOST = ResidencyReport(
    serving=False,
    detail="the usual assistant could not be reloaded after a deep task; recovery is manual",
)

# Boot recovery ran and did not leave the cortex serving: the model host was unreachable, or the
# cortex never reported ready inside the load bound. Distinct from the one above because no deep
# task need have happened; this is the state a brain starts in when the GPU is already wrong.
RESIDENCY_BOOT_FAILED = ResidencyReport(
    serving=False,
    detail="the usual assistant did not come up at startup; the model host needs attention",
)
