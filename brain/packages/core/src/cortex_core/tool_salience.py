"""Which calls deserve dispatching: the ``SaliencePolicy`` port and the two policies that ship.

The third and last bound on the tool loop (ADR-0009 salience addendum, closing decision 3's
open half). ``tool_loop.py`` owns how *long* a loop runs, ``tool_budget.py`` how much it may
*spend*, and this module whether a call is worth making at all.

A policy reads exactly one thing: the calls this loop has already dispatched, grouped by the
round that emitted them. It never predicts whether a call will be *useful*, which is the model's
judgment and cannot be made deterministically in a pure core; it only recognizes a call the loop
has already made. That scope is per **loop**, unlike the turn-wide budget: reach into the outside
world is a resource a turn's subagents share, while a repeat is redundant only against the
message list that already holds its answer, and a subagent cannot see a sibling's results. The
scoping needs no enforcement, since the dispatched calls are a local of ``stream_tool_loop`` and
a policy is stateless.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from cortex_core.tools import ToolCall

# How many times one identical call may be dispatched in a single loop. Two rather than one,
# decided on which failure is benign: refusing the second denies information the model legitimately
# asked for (a retry after a transient failure, or a re-read of something the turn itself just
# changed), while allowing it wastes at most one dispatch of a pool of MAX_TOOL_DISPATCHES. The
# third identical attempt is a model spinning, and no reading of it is legitimate.
MAX_IDENTICAL_DISPATCHES = 2


class SaliencePolicy(Protocol):
    """Decides whether one tool call is worth dispatching, given what this loop already ran.

    ``dispatched`` is the loop's calls grouped by round, oldest first, the last group being the
    round in progress (empty until that round dispatches its first call). The grouping belongs
    to the port rather than to an implementation: whether a repeat can inform anything turns on
    whether the model has *seen* a result since it last asked, and only a round boundary answers
    that. A policy that does not care simply ignores the grouping.
    """

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool: ...


class AlwaysSalient:
    """Every call deserves dispatch: the loop's behavior before this policy existed.

    ``CORTEX_TOOLS_SALIENCE=off`` selects it, so a deployment can restore the unfiltered loop
    exactly. It is not the default, because a bound that ships off protects nobody.
    """

    def admits(self, call: ToolCall, dispatched: Sequence[Sequence[ToolCall]]) -> bool:
        """Admit unconditionally; neither the call nor the history is consulted."""
        del call, dispatched  # nothing is filtered
        return True


@dataclass(frozen=True, slots=True)
class RepeatSalience:
    """At most one identical call per round, and at most ``limit`` of them per loop.

    Two clauses, because they answer different questions. **Within** a round the model chose
    every call before seeing any of that round's results, so an identical twin cannot learn
    anything the first did not, and there is no legitimate case for it: that clause is absolute.
    **Across** rounds the model has read a result and asked again, which is legitimate (a retry,
    or a re-observation), so that clause is a cap rather than a prohibition.

    Identity is the call's ``name`` plus its ``arguments``. ``id`` is excluded because it is
    unique per call by construction, and ``stamp`` because the dispatcher overwrites it with the
    turn's; what remains is exactly what the model chose. Arguments compare structurally, so key
    order does not matter and two spellings of one intent (``a.txt`` and ``./a.txt``) are two
    different calls, which is the conservative direction: an unrecognized repeat is dispatched.

    ``limit`` must be positive. A limit of zero would refuse every call including the first,
    which is a silent hole rather than a visible failure (the loop would run its rounds, dispatch
    nothing, and report refusals the model cannot act on), so it is rejected at construction like
    a non-positive tool price.
    """

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


# Both policies are stateless and immutable, so one shared instance of each is safe and lets a
# default argument be a plain value (the RAW_RECALL_POLICY precedent).
ALWAYS_SALIENT = AlwaysSalient()
REPEAT_SALIENCE = RepeatSalience()
