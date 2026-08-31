"""The subagent roster: the candidate models and the resources each one runs with."""

from collections.abc import Mapping
from dataclasses import dataclass

from cortex_core.placement import PlacementRequest, PlacementTarget
from cortex_core.ports import InferenceBackend, SubagentPlacer, SubagentScheduler


@dataclass(frozen=True, slots=True)
class SubagentResources:
    """One subagent entry's placement machinery, bundled so the runner takes it as a unit."""

    backends: Mapping[PlacementTarget, InferenceBackend]
    scheduler: SubagentScheduler
    placer: SubagentPlacer
    request: PlacementRequest


@dataclass(frozen=True, slots=True)
class SubagentProfile:
    """One roster entry: the machinery that runs it, plus the trade-offs the spec advertises."""

    resources: SubagentResources
    description: str = ""


@dataclass(frozen=True, slots=True)
class SubagentRoster:
    """The candidate subagent models, keyed by advertised name, plus the default entry."""

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
        """Pick the entry to run: the default for a restricted task, then the cortex's choice."""
        if tainted or tools_enabled:
            return self.default
        if not requested:
            return self.default
        return requested if requested in self.entries else None
