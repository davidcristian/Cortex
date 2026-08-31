"""Placement value types: where a subagent runs, and what it reserves (pure data, see ADR-0012).

These live here, importing no ports, so ``ports.py`` can depend on them without a cycle exactly
as ``subagents.py`` and ``tools.py`` do. A ``SubagentPlacer`` fit-tests one ``PlacementRequest``
against the VRAM soft cap and returns a ``Placement``, the whole model on GPU (``-ngl 99``) when it
fits, else CPU-only (``-ngl 0``), never a partial straddle. The core decides the target and
accounts for the VRAM; the host half starts the ``llama-server`` with the matching ``-ngl`` flag.
"""

from dataclasses import dataclass
from enum import Enum

_NGL_ALL = 99  # every layer on the GPU
_NGL_NONE = 0  # every layer on the CPU


class PlacementTarget(Enum):
    """Where the whole subagent model runs, either GPU or CPU, never a partial GPU+CPU straddle."""

    GPU = "gpu"
    CPU = "cpu"

    @property
    def ngl(self) -> int:
        """The llama.cpp ``-ngl`` flag this target implies: 99 (whole model on GPU) or 0 (CPU).

        The number the host uses to start the placed ``llama-server``; the core never spawns a
        process, so it only decides the value (target and ngl are isomorphic, one field not two).
        """
        return _NGL_ALL if self is PlacementTarget.GPU else _NGL_NONE


@dataclass(frozen=True, slots=True)
class PlacementRequest:
    """One subagent asking to be placed: its logical id and the resources it needs.

    ``vram_gb`` is the estimated whole-model GPU footprint (weights + KV at the subagent context)
    the placer fit-tests against headroom; ``cpus``/``memory_gb`` are the per-container ``--cpus``/
    ``--memory`` charge the scheduler sums into its soft budget. All must be positive. A
    non-positive resource ask is a wiring error, raised here rather than mis-placing the spawn.
    """

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
    """A ``SubagentPlacer``'s decision for one spawn: where it runs and the VRAM it reserved.

    ``target`` is the routing key (the runner picks the GPU or CPU backend). ``reserved_gb`` is the
    VRAM debited from the ledger (the request's ``vram_gb`` on GPU, ``0.0`` on CPU), so ``release``
    frees exactly that with no back-reference to the request.
    """

    target: PlacementTarget
    reserved_gb: float
