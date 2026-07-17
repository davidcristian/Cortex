"""How much of the outside world one turn may touch: the budget, and what tools cost."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

MAX_TOOL_DISPATCHES = 32

_NO_COSTS: Mapping[str, int] = MappingProxyType({})

DEFAULT_TOOL_COST = 1


@dataclass(frozen=True, slots=True)
class ToolCostPolicy:
    """Per-tool dispatch prices by advertised tool name, defaulting to ``DEFAULT_TOOL_COST``."""

    costs: Mapping[str, int] = _NO_COSTS

    def __post_init__(self) -> None:
        if bad := sorted(name for name, cost in self.costs.items() if cost < 1):
            msg = f"tool costs must be positive: {bad}"
            raise ValueError(msg)
        object.__setattr__(self, "costs", MappingProxyType(dict(self.costs)))

    def cost_of(self, name: str) -> int:
        """What dispatching ``name`` spends; unpriced tools cost ``DEFAULT_TOOL_COST``."""
        return self.costs.get(name, DEFAULT_TOOL_COST)


UNIFORM_COST = ToolCostPolicy()


class DispatchBudget:
    """One turn's dispatch allowance, shared by every tool loop that turn runs."""

    def __init__(self, limit: int = MAX_TOOL_DISPATCHES, *, closed: bool = False) -> None:
        self._limit = limit
        self._spent = 0
        self._closed = closed

    @classmethod
    def resume(cls, *, remaining: int, closed: bool) -> "DispatchBudget":
        """Rebuild a pool at a persisted position: the brain phase after a swap."""
        return cls(remaining, closed=closed)

    @property
    def limit(self) -> int:
        """The total this pool may spend before it closes."""
        return self._limit

    @property
    def spent(self) -> int:
        """What has been charged so far, summed across every loop sharing this pool."""
        return self._spent

    @property
    def closed(self) -> bool:
        """Whether a call has already failed to fit, after which nothing else is admitted."""
        return self._closed

    def charge(self, cost: int) -> bool:
        """Spend ``cost`` if it fits, reporting whether the call it prices may run."""
        # A call that does not fit closes the pool rather than being skipped so cheaper calls
        # behind it get through, so what a turn spends does not depend on the order the model
        # emitted its calls in, nor on which of a concurrent batch of subagents charged first.
        if self._closed or self._spent + cost > self._limit:
            self._closed = True
            return False
        self._spent += cost
        return True
