"""How much of the outside world one turn may touch: the budget, and what tools cost.

``tool_loop.py`` owns how long a loop runs (``MAX_TOOL_STEPS`` rounds); this module owns how much
it may spend doing so. The two are deliberately separate bounds (ADR-0009 budget addendum), and
the spend side is a currency of its own: a total, a price per tool, and the pool they are spent
from.

The budget the ADR-0009 budget addendum landed counted calls: thirty two filesystem reads and
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

# Upper bound on what one TURN may spend on tool dispatches, across every round of every loop
# it runs (ADR-0009 budget addendum, widened from one loop to the turn by the turn-wide
# addendum). MAX_TOOL_STEPS bounds rounds, not calls: a single round dispatched every call the
# model emitted, so the two bounds multiplied and neither answered "how many external calls can
# one turn make?". This one does. Sized above plausible legitimate use (eight rounds averaging
# four calls) and far below spam. Past it, calls are refused, audited, and reported to the
# model, which is why the total is a pool rather than a per-round cap.
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
    budget would bound nothing on exactly the tool a user cared enough about to configure, and
    nothing would report that. It is rejected at construction instead, and the composition root's
    config validation turns it into a boot failure.
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


class DispatchBudget:
    """One turn's dispatch allowance, shared by every tool loop that turn runs (ADR-0009).

    The budget started as an ``int`` on ``ToolLoopContext``, which made it per loop invocation:
    a subagent's fresh context started a fresh count, so a turn that delegated spent the total
    once for itself and again for every subagent. This is that counter made an object, so the
    cortex loop and each spawned subagent hold the same pool and the turn has one answer to
    "how much of the outside world did this reach?".

    Mutable and shared on purpose, which the rest of the core is not; it is a resource handle
    rather than a value, so it is compared by identity and the ``TurnStamp`` that carries it
    excludes it from equality. Sharing is safe without a lock because ``charge`` never awaits: a
    batch of subagents runs concurrently under ``asyncio.gather``, but on one event loop no two
    charges can interleave.

    The pool itself is never persisted; its position is. A handoff record carries what is left and
    whether the pool closed (ADR-0030 decision 2), and ``resume`` rebuilds a pool from that. The
    allowance bounds one turn's reach across the swap too, so a swap can never refill it (the one
    hard rule is about not losing state, which includes state that is a limit).
    """

    def __init__(self, limit: int = MAX_TOOL_DISPATCHES, *, closed: bool = False) -> None:
        self._limit = limit
        self._spent = 0
        self._closed = closed

    @classmethod
    def resume(cls, *, remaining: int, closed: bool) -> "DispatchBudget":
        """Rebuild a pool at a persisted position: the brain phase after a swap (ADR-0030).

        The new pool's ``limit`` is what was left, spending nothing yet, which is the same
        bound the turn had when it escalated; a pool that had already closed stays closed, so a
        swap cannot hand a runaway turn a fresh allowance. What was already spent is not carried
        as a number because nothing reads it: the refusal the model gets depends only on whether
        the next call fits and on whether the pool is closed.
        """
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
        """Spend ``cost`` if it fits, reporting whether the call it prices may run.

        A call that does not fit closes the pool for good, rather than being skipped so that
        cheaper calls behind it still get through (ADR-0009 cost addendum, now at the turn's
        scale). Two reasons, both of which get stronger once subagents share the pool: the
        refusal the model reads tells it to stop calling tools entirely, which a pool that kept
        admitting small calls would contradict; and the turn's spend would otherwise depend on
        the order the model emitted its calls in, and on which of a concurrent batch of
        subagents happened to charge first. A refused call is charged nothing, so what makes the
        refusal stick is the closure rather than the arithmetic.
        """
        if self._closed or self._spent + cost > self._limit:
            self._closed = True
            return False
        self._spent += cost
        return True
