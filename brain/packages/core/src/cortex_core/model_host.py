"""What a model process can be doing, and the plan one GPU's residency swap follows (ADR-0030)."""

from dataclasses import dataclass
from enum import Enum

# How long a swap waits for the model it started to report READY (ADR-0030 decision 4 step 3).
# An 18 GB GGUF read off the drvfs model mount at the measured ~150-180 MB/s is minutes, so the
# default is generous; the deployment overrides it with CORTEX_SWAP_LOAD_TIMEOUT_S.
DEFAULT_SWAP_LOAD_TIMEOUT_S = 300.0

DEFAULT_SWAP_DRAIN_TIMEOUT_S = 60.0

# How long the readiness gate waits between two ``status`` polls. A load takes minutes, so a
# second-scale poll costs nothing and keeps the gate's own latency below the noise floor.
DEFAULT_HEALTH_POLL_INTERVAL_S = 1.0


class ModelHostState(Enum):
    """What one logical model's process is doing, as its host reports it (ADR-0030 decision 3)."""

    STOPPED = "stopped"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DeviceMemory:
    """How much of the GPU is free right now, and how big it is, as the host's own card reports."""

    free_mib: int
    total_mib: int


@dataclass(frozen=True, slots=True)
class ResidencyPlan:
    """Which models share the one GPU, and the bounds a swap between them respects (ADR-0030)."""

    cortex_model: str
    brain_model: str
    evict_models: tuple[str, ...] = ()
    coresident: bool = False
    brain_vram_mib: int = 0
    drain_timeout_s: float = DEFAULT_SWAP_DRAIN_TIMEOUT_S
    load_timeout_s: float = DEFAULT_SWAP_LOAD_TIMEOUT_S
    poll_interval_s: float = DEFAULT_HEALTH_POLL_INTERVAL_S

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
