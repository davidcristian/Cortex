"""What a model process can be doing, and the plan one GPU's residency swap follows (ADR-0030).

Pure values, shared by the three objects the swap composes: ``SwappingModelManager`` (which
performs the process swap inside its residency scope), the boot-recovery convergence, and the
readiness gate in ``health_gate.py``. Deliberately free of port imports so the ``ModelHost``
protocol can name ``ModelHostState`` without a cycle.

A logical model id (ADR-0004) is the only identifier that crosses any of these seams: artifact
paths, ports, ``-ngl`` and context flags belong to whatever supervises the processes, never here.
"""

from dataclasses import dataclass
from enum import Enum

# How long a swap waits for the model it started to report READY (ADR-0030 decision 4 step 3).
# An 18 GB GGUF read off the drvfs model mount at the measured ~150-180 MB/s is minutes, so the
# default is generous; the deployment overrides it with CORTEX_SWAP_LOAD_TIMEOUT_S.
DEFAULT_SWAP_LOAD_TIMEOUT_S = 300.0

# How long a swap waits for the subagent pool to quiesce before it evicts anything (ADR-0030
# decision 4 step 2). Generous enough for a normal delegated run to finish, short enough that a
# wedged one does not hold the user's handoff open for minutes; the deployment overrides it with
# CORTEX_SWAP_DRAIN_TIMEOUT_S.
DEFAULT_SWAP_DRAIN_TIMEOUT_S = 60.0

# How long the readiness gate waits between two ``status`` polls. A load takes minutes, so a
# second-scale poll costs nothing and keeps the gate's own latency below the noise floor.
DEFAULT_HEALTH_POLL_INTERVAL_S = 1.0

# What one of this repo's VRAM knobs means in the unit every instrument here reports. ``nvidia-smi``
# and the plan's own ``brain_vram_mib`` speak MiB, while the placer's budget knobs
# (``CORTEX_VRAM_SOFT_CAP_GB``, ``CORTEX_VRAM_CORTEX_GB``) speak the gibibyte that divides it, which
# is the same unit those knobs were measured in (ADR-0012, ADR-0030 co-residency addendum).
_MIB_PER_GB = 1024.0


class ModelHostState(Enum):
    """What one logical model's process is doing, as its host reports it (ADR-0030 decision 3).

    ``STOPPED`` (no process), ``LOADING`` (started, weights not served yet), ``READY`` (serving,
    which is what the compose healthcheck means today), ``FAILED`` (the process died or could not
    load). ``start`` only *begins* loading, so readiness is observed here and nowhere else, which
    is why the swap has an explicit health gate rather than trusting a returned ``start``.
    """

    STOPPED = "stopped"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DeviceMemory:
    """How much of the GPU is free right now, and how big it is, as the host's own card reports.

    MiB because every instrument and every measurement in this repo speaks MiB (``nvidia-smi``,
    ADR-0004's tier costs, the ADR-0030 co-residency table), so a value never has to be converted
    at the seam where it is compared.

    **A reading is only evidence before an allocation, never after one.** Measured 2026-08-07: a
    pair of tiers that genuinely fit a 24 GB card and a pair overcommitted by 4676 MiB both read
    about 23.6 GB used with about 0.5 GB free, because the WSL2 driver pages the overcommit to
    system memory instead of refusing it, and the only witness is decode throughput. So this value
    answers exactly one question, "is there room for what is about to be loaded", asked while the
    room still exists.
    """

    free_mib: int
    total_mib: int


@dataclass(frozen=True, slots=True)
class ResidencyPlan:
    """Which models share the one GPU, and the bounds a swap between them respects (ADR-0030).

    ``cortex_model`` is the standing resident every exit path converges back to;
    ``brain_model`` is the deep model a handoff swaps in. ``evict_models`` names the other
    hosted models standing beside the cortex (the GPU-placed subagent, when one is hosted):
    boot recovery brings them up, and by default a swap stops them first, because while the
    brain is resident it is alone on the GPU (ADR-0030 decision 8).

    ``coresident`` is the deployment's opt-in reversal of exactly that default, off unless a
    deployment has measured that its standing peers fit beside the deep model (the ADR's
    co-residency addendum). With it on a swap stops the cortex and nothing else, and the
    subagent pool is never quiesced, so delegated work keeps flowing through the handoff and
    the deep model's own phase may spawn. It is safe to reopen admission precisely because
    nothing admission could be handed to was ever stopped.

    ``brain_vram_mib`` is what turns that assertion into something checkable: the free device
    memory the deep model needs before it may be started, measured by the deployment on its own
    card. Zero (the default) means no fit check at all, which is the shipped behaviour; anything
    positive makes ``swap_in`` read the host's card immediately before the load and refuse the
    handoff when the room is not there. It is required alongside ``coresident`` on a deployment
    whose host can see a card, because a co-resident plan is precisely a claim about room.

    ``drain_timeout_s`` bounds the wait for the subagent pool to quiesce, which happens before
    anything is evicted, so exceeding it aborts the swap rather than killing a subagent;
    ``load_timeout_s`` bounds the readiness gate after a start, and ``poll_interval_s`` is the
    wait between two status polls. Composition-root config, handed down as one value so the
    manager, the conductor, and boot recovery cannot disagree about the topology.
    """

    cortex_model: str
    brain_model: str
    evict_models: tuple[str, ...] = ()
    coresident: bool = False
    brain_vram_mib: int = 0
    drain_timeout_s: float = DEFAULT_SWAP_DRAIN_TIMEOUT_S
    load_timeout_s: float = DEFAULT_SWAP_LOAD_TIMEOUT_S
    poll_interval_s: float = DEFAULT_HEALTH_POLL_INTERVAL_S

    @property
    def brain_vram_gb(self) -> float:
        """The same declared cost in the unit the subagent placer's budget is written in.

        One conversion in one place, because the two halves of this arithmetic were measured with
        different instruments: the fit check compares MiB against what the card reports, and the
        placer's handoff charge compares gibibytes against a soft cap the deployment set. Zero
        stays zero, which is the "nothing declared" case both readers test for.
        """
        return self.brain_vram_mib / _MIB_PER_GB

    def __post_init__(self) -> None:
        if self.brain_vram_mib < 0:
            msg = f"ResidencyPlan.brain_vram_mib must be >= 0, got {self.brain_vram_mib}"
            raise ValueError(msg)
        if self.drain_timeout_s < 0:
            msg = f"ResidencyPlan.drain_timeout_s must be >= 0, got {self.drain_timeout_s}"
            raise ValueError(msg)
        if self.load_timeout_s < 0:
            msg = f"ResidencyPlan.load_timeout_s must be >= 0, got {self.load_timeout_s}"
            raise ValueError(msg)
        if self.poll_interval_s <= 0:
            msg = f"ResidencyPlan.poll_interval_s must be > 0, got {self.poll_interval_s}"
            raise ValueError(msg)
