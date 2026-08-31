"""Placement value types: where a subagent runs, and what it reserves (pure data)."""

from dataclasses import dataclass
from enum import Enum

_NGL_ALL = 99
_NGL_NONE = 0


class PlacementTarget(Enum):
    """Where the whole subagent model runs, either GPU or CPU, never a partial GPU+CPU straddle."""

    GPU = "gpu"
    CPU = "cpu"

    @property
    def ngl(self) -> int:
        """The llama.cpp ``-ngl`` flag this target implies: 99 (whole model on GPU) or 0 (CPU)."""
        return _NGL_ALL if self is PlacementTarget.GPU else _NGL_NONE


@dataclass(frozen=True, slots=True)
class PlacementRequest:
    """One subagent asking to be placed: its logical id and the resources it needs."""

    model: str
    vram_gb: float
    cpus: float
    memory_gb: float

    def __post_init__(self) -> None:
        if self.vram_gb <= 0 or self.cpus <= 0 or self.memory_gb <= 0:
            msg = "PlacementRequest.vram_gb, cpus, and memory_gb must all be > 0"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Placement:
    """A ``SubagentPlacer``'s decision for one spawn: where it runs and the VRAM it reserved."""

    target: PlacementTarget
    reserved_gb: float
