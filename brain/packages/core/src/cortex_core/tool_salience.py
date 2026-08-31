"""Which calls are worth dispatching: the ``SaliencePolicy`` port and the two policies that ship."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from cortex_core.tools import ToolCall

# Two rather than one: a second identical call can be a retry after a transient failure or a
# re-read of something the turn itself just changed, while a third is the model repeating itself.
MAX_IDENTICAL_DISPATCHES = 2


class SaliencePolicy(Protocol):
    """Decides whether one tool call is worth dispatching, given what this loop already ran."""

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool: ...


class AlwaysSalient:
    """Every call is dispatched: the loop's behavior before this policy existed."""

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Admit unconditionally; neither the call nor the history is consulted."""
        del call, dispatched
        return True


@dataclass(frozen=True, slots=True)
class RepeatSalience:
    """At most one identical call per round, and at most ``limit`` of them per loop."""

    limit: int = MAX_IDENTICAL_DISPATCHES

    def __post_init__(self) -> None:
        if self.limit < 1:
            msg = f"salience limit must be positive: {self.limit}"
            raise ValueError(msg)

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Whether ``call`` is worth dispatching given the rounds already dispatched."""
        current = dispatched[-1] if dispatched else ()
        if any(_asks_the_same(call, other) for other in current):
            return False
        already = sum(
            1 for previous in dispatched for other in previous if _asks_the_same(call, other)
        )
        return already < self.limit


def _asks_the_same(call: ToolCall, other: ToolCall) -> bool:
    """Whether two calls ask the same thing: same tool, same arguments."""
    return call.name == other.name and call.arguments == other.arguments


ALWAYS_SALIENT = AlwaysSalient()
REPEAT_SALIENCE = RepeatSalience()
