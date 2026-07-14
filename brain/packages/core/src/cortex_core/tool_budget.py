"""How much of the outside world one tool loop may touch: the budget, and what tools cost."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

MAX_TOOL_DISPATCHES = 32

# The empty price list, as an immutable mapping so it can be a shared field default.
_NO_COSTS: Mapping[str, int] = MappingProxyType({})

# What a call costs when the policy prices it by name. One, so a budget of N is N calls for
# every unpriced tool: the count semantics the budget shipped with remain the default, and a
# deployment opts into weighting one tool at a time rather than restating the whole tool set.
DEFAULT_TOOL_COST = 1


@dataclass(frozen=True, slots=True)
class ToolCostPolicy:
    """Per-tool dispatch prices by advertised tool name, defaulting to ``DEFAULT_TOOL_COST``."""

    costs: Mapping[str, int] = _NO_COSTS

    def __post_init__(self) -> None:
        if bad := sorted(name for name, cost in self.costs.items() if cost < 1):
            msg = f"tool costs must be positive: {bad}"
            raise ValueError(msg)
        # Freeze the caller's mapping into the policy: a frozen dataclass holding a live dict
        # would let whoever built it keep editing prices after the fact.
        object.__setattr__(self, "costs", MappingProxyType(dict(self.costs)))

    def cost_of(self, name: str) -> int:
        """What dispatching ``name`` spends; unpriced tools cost ``DEFAULT_TOOL_COST``."""
        return self.costs.get(name, DEFAULT_TOOL_COST)


# The policy every dispatcher gets unless the composition root passes one: every tool costs
# one, which is the plain call count the budget started as.
UNIFORM_COST = ToolCostPolicy()
