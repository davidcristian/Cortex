"""How much of the outside world one tool loop may touch: the budget, and what tools cost.

``tool_loop.py`` owns how *long* a loop runs (``MAX_TOOL_STEPS`` rounds); this module owns how
much it may *spend* doing so. The two are deliberately separate bounds (ADR-0009 budget
addendum), and the spend side is a currency of its own: a total, and a price per tool.

The budget the ADR-0009 budget addendum landed counted *calls*: thirty two filesystem reads and
thirty two ``spawn_subagents`` batches spent it identically, though only one of those is thirty
two fan-outs of model runs. The cost addendum makes the unit a price, so one total can charge a
tool by what running it actually costs, and an unpriced tool still costs one.

Like the gated-name set (ADR-0022), a price is declared by the composition root and is never
read off a ``ToolSpec``: a sidecar that advertised its own price would be setting its own
spending limit, which is exactly the authority a remote tool server must not hold. The policy is
consulted by ``stream_tool_loop`` through the dispatcher that holds it, so a caller outside any
tool loop (the schedule ticker's direct dispatch) is unaffected by construction.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

# Upper bound on what one loop may spend on tool dispatches across ALL its rounds (ADR-0009
# budget addendum). MAX_TOOL_STEPS bounds rounds, not calls: a single round dispatched every
# call the model emitted, so the two bounds multiplied and neither answered "how many external
# calls can one turn make?". This one does. Sized above plausible legitimate use (eight rounds
# averaging four calls) and far below spam. Past it, calls are refused, audited, and reported
# to the model, which is why the total is per loop rather than per round.
MAX_TOOL_DISPATCHES = 32

# The empty price list, as an immutable mapping so it can be a shared field default.
_NO_COSTS: Mapping[str, int] = MappingProxyType({})

# What a call costs when the policy prices it by name. One, so a budget of N is N calls for
# every unpriced tool: the count semantics the budget shipped with remain the default, and a
# deployment opts into weighting one tool at a time rather than restating the whole tool set.
DEFAULT_TOOL_COST = 1


@dataclass(frozen=True, slots=True)
class ToolCostPolicy:
    """Per-tool dispatch prices by advertised tool name, defaulting to ``DEFAULT_TOOL_COST``.

    Prices must be positive: a zero or negative cost would make a tool free to call, so the
    budget would bound nothing on exactly the tool a user cared enough about to configure.
    That is a silent hole rather than a visible failure, so it is rejected at construction and
    the composition root's config validation turns it into a boot failure.
    """

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
