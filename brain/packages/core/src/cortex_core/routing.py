"""Pure routing decision: which model tier handles a user turn (no I/O)."""

from dataclasses import dataclass
from enum import Enum


class Tier(Enum):
    """The three model tiers sharing the GPU (docs/adr/ADR-0001-architecture.md)."""

    CORTEX = "cortex"
    SUBAGENT = "subagent"
    BRAIN = "brain"


@dataclass(frozen=True, slots=True)
class RoutingHints:
    """Signals about a user turn that inform the tier choice."""

    explicit_tier: Tier | None = None
    needs_deep_reasoning: bool = False
    is_narrow_delegable: bool = False


def route_turn(hints: RoutingHints) -> Tier:
    """Pick a tier by precedence: explicit override, then BRAIN, then SUBAGENT, else CORTEX."""
    if hints.explicit_tier is not None:
        return hints.explicit_tier
    if hints.needs_deep_reasoning:
        return Tier.BRAIN
    if hints.is_narrow_delegable:
        return Tier.SUBAGENT
    return Tier.CORTEX
