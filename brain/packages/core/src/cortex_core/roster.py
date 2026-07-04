"""The subagent roster: candidate models, their resources, and the ADR-0017 boundary.

Slice 8.6 (ADR-0018) lets the cortex pick the subagent model per spawn. This module holds the
pure values that make that safe: ``SubagentResources`` (one entry's placement machinery, moved
here from ``runner.py`` so the roster can bundle it without an import cycle), ``SubagentProfile``
(resources plus the trade-offs advertised to the cortex), and ``SubagentRoster``, whose
``resolve`` is where ADR-0017 executes: the cortex's model choice is an optimization *hint, not
authority*, and any spawn path that can carry untrusted content runs the injection-robust
default, deterministically. Enforcing here (the runner calls it per task) rather than in the
spawn tool means a task reaching the store by any path still resolves safely.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from cortex_core.placement import PlacementRequest, PlacementTarget
from cortex_core.ports import InferenceBackend, SubagentPlacer, SubagentScheduler


@dataclass(frozen=True, slots=True)
class SubagentResources:
    """One subagent entry's placement machinery, bundled so the runner takes it as a unit
    (ADR-0012).

    ``backends`` maps each target to its ``InferenceBackend`` (the GPU sidecar and the CPU one);
    ``scheduler`` is the soft CPU/RAM budget; ``placer`` is the VRAM-budget accountant; ``request``
    is this entry's resource ask (its ``model`` is the id handed to the backend). Mirrors
    VRAM ledger, per ADR-0018); only ``backends`` and ``request`` differ per entry.
    ``scheduler`` and ``placer`` are the SAME objects in every entry (one machine, one budget, one
    ``TurnCapabilities`` (collaborators that always travel together). In a multi-entry roster the
    """

    backends: Mapping[PlacementTarget, InferenceBackend]
    scheduler: SubagentScheduler
    placer: SubagentPlacer
    request: PlacementRequest


@dataclass(frozen=True, slots=True)
class SubagentProfile:
    """One roster entry: the machinery that runs it, plus the trade-offs the spec advertises.

    ``description`` is what the cortex reads when choosing (size/latency and
    injection-robustness, ADR-0004); it informs the *optimization* only, since safety is
    ``SubagentRoster.resolve``'s, which no description can weaken.
    """

    resources: SubagentResources
    description: str = ""


@dataclass(frozen=True, slots=True)
class SubagentRoster:
    """The candidate subagent models, keyed by advertised name, with the forced-robust default.

    ``default`` names the injection-robust ADR-0004 pick, the entry every untrusted-content
    path is pinned to (ADR-0017). Construction fails on an empty roster or a default that is
    not an entry: a roster that cannot resolve safely is a wiring error, caught here.
    """

    entries: Mapping[str, SubagentProfile]
    default: str

    def __post_init__(self) -> None:
        if not self.entries:
            msg = "SubagentRoster.entries must not be empty"
            raise ValueError(msg)
        if self.default not in self.entries:
            msg = f"SubagentRoster.default {self.default!r} is not a roster entry"
            raise ValueError(msg)

    def resolve(self, requested: str, *, tainted: bool, tools_enabled: bool) -> str | None:
        """The entry to run is ADR-0017's boundary, then the cortex's choice, else ``None``.

        A spawn that can carry untrusted content (the spawning turn was ``tainted`` at spawn
        time, or the subagent is ``tools_enabled`` and can fetch untrusted content itself)
        resolves to the robust ``default`` whatever was requested, unknown names included: on
        an untrusted path the only safe answer is the default. Otherwise the requested entry
        is honored (``""`` means the default), and an unknown name resolves to ``None``. The
        runner persists that as an ``ok=False`` result, fail closed, mirroring "task not found".
        """
        if tainted or tools_enabled:
            return self.default
        if not requested:
            return self.default
        return requested if requested in self.entries else None
