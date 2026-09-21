"""What a model process can be doing, and the plan one GPU's residency swap follows."""

from dataclasses import dataclass
from enum import Enum

# 300 s: a load reads an 18 GB GGUF off the model mount at 150 to 180 MB/s, so it takes
# minutes. A deployment overrides it with CORTEX_SWAP_LOAD_TIMEOUT_S.
DEFAULT_SWAP_LOAD_TIMEOUT_S = 300.0

# A whole CPU subtask takes 200 to 300 s, so a drain that meets one in flight usually runs out
# and aborts the handoff with nothing evicted, which is the intended direction.
DEFAULT_SWAP_DRAIN_TIMEOUT_S = 60.0

DEFAULT_HEALTH_POLL_INTERVAL_S = 1.0

# The subagent placer's budget settings are in gibibytes, so this converts MiB to those.
_MIB_PER_GB = 1024.0


class ModelHostState(Enum):
    """What one logical model's process is doing, as its host reports it."""

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
class ControlBounds:
    """How long one control call to a model host may legitimately take, in its three terms."""

    probe_timeout_s: float
    stop_grace_s: float
    reap_timeout_s: float

    @property
    def worst_case_stop_s(self) -> float:
        """The slowest legitimate stop: a queued probe, then the grace, then the reap."""
        return self.probe_timeout_s + self.stop_grace_s + self.reap_timeout_s

    def clears(self, deadline_s: float) -> bool:
        """Whether ``deadline_s`` sits strictly above that worst case."""
        return self.worst_case_stop_s < deadline_s

    def pairing_fields(self, deadline_s: float) -> dict[str, float]:
        """The five numbers as log-record fields, so one line names each of them."""
        return {
            "deadline_s": deadline_s,
            "worst_s": self.worst_case_stop_s,
            "probe_timeout_s": self.probe_timeout_s,
            "stop_grace_s": self.stop_grace_s,
            "reap_timeout_s": self.reap_timeout_s,
        }


@dataclass(frozen=True, slots=True)
class ResidencyPlan:
    """Which models share the one GPU, and the bounds a swap between them respects."""

    cortex_model: str
    brain_model: str
    evict_models: tuple[str, ...] = ()
    coresident: bool = False
    brain_vram_mib: int = 0
    brain_decode_tps: float = 0.0
    drain_timeout_s: float = DEFAULT_SWAP_DRAIN_TIMEOUT_S
    load_timeout_s: float = DEFAULT_SWAP_LOAD_TIMEOUT_S
    poll_interval_s: float = DEFAULT_HEALTH_POLL_INTERVAL_S
    control_deadline_s: float = 0.0

    @property
    def brain_vram_gb(self) -> float:
        """The declared cost in gibibytes, the unit the subagent placer's budget uses."""
        return self.brain_vram_mib / _MIB_PER_GB

    def __post_init__(self) -> None:
        if self.brain_vram_mib < 0:
            msg = f"ResidencyPlan.brain_vram_mib must be >= 0, got {self.brain_vram_mib}"
            raise ValueError(msg)
        if self.brain_decode_tps < 0:
            msg = f"ResidencyPlan.brain_decode_tps must be >= 0, got {self.brain_decode_tps}"
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
        if self.control_deadline_s < 0:
            msg = f"ResidencyPlan.control_deadline_s must be >= 0, got {self.control_deadline_s}"
            raise ValueError(msg)
        self._refuse_listed_residents()

    def _refuse_listed_residents(self) -> None:
        """Refuse an evict list naming the deep model or the cortex."""
        for tier, setting in (
            (self.brain_model, "CORTEX_MODEL_BRAIN"),
            (self.cortex_model, "CORTEX_MODEL_CORTEX"),
        ):
            if tier in self.evict_models:
                msg = (
                    f"ResidencyPlan.evict_models (CORTEX_SWAP_EVICT_MODELS) names {tier!r}, "
                    f"which is {setting}; list only the peers that run beside the cortex"
                )
                raise ValueError(msg)
