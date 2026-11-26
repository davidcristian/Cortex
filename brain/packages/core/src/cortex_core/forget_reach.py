"""The stored rows a request to forget reaches beside the rows recall ranked for the turn."""

from collections.abc import Sequence
from dataclasses import dataclass

from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.memory_request import asks_to_forget
from cortex_core.memory_values import whole_values
from cortex_core.recall import MemoryRecaller

# As many rows as recall ranks, so a forget turn shows at most twice the rows of another turn.
FORGET_REACH_LIMIT = 5


def more_held_note(value: str) -> str:
    """The memory context's line saying rows the request does not show also hold ``value``."""
    return f"More stored memories hold {value} than are shown here."


@dataclass(frozen=True, slots=True)
class ForgetReach:
    """The rows found for each value a request to forget names, and the rows nearest it."""

    found: tuple[tuple[str, tuple[MemoryRecord, ...]], ...]
    nearest: tuple[MemoryRecord, ...] = ()

    def added(self, hits: Sequence[ScoredMemory]) -> Sequence[ScoredMemory]:
        """Up to ``FORGET_REACH_LIMIT`` reached rows that ``hits`` does not hold, oldest first."""
        rows = [row for _, found in self.found for row in found[:FORGET_REACH_LIMIT]]
        held = {hit.record.id for hit in hits}
        added = {row.id: row for row in (*rows, *self.nearest) if row.id not in held}
        return [ScoredMemory(record=row, score=0.0) for row in added.values()][:FORGET_REACH_LIMIT]

    def unshown(self, shown: Sequence[ScoredMemory]) -> tuple[str, ...]:
        """Each value held by a stored row that ``shown`` does not hold."""
        ids = {hit.record.id for hit in shown}
        return tuple(value for value, found in self.found if any(r.id not in ids for r in found))


async def forget_reach(
    query: str, memory: MemoryRecaller, *, session_id: str, ranked: int
) -> ForgetReach | None:
    """What a request to forget in ``query`` reaches, or None when it asks no forget.

    Each value's search returns one row more than ``ranked`` and the reach can show together.
    """
    keeping = asks_to_forget_keeping(query)
    if not keeping and not asks_to_forget(query):
        return None
    values = whole_values(query)
    limit = ranked + FORGET_REACH_LIMIT + 1
    found = [
        (form, tuple(await memory.find_value(key, session_id=session_id, limit=limit)))
        for key, form in values.items()
    ]
    nearest: Sequence[MemoryRecord] = ()
    if keeping and not values:
        nearest = await memory.nearest(query, session_id=session_id, limit=FORGET_REACH_LIMIT)
    return ForgetReach(found=tuple(found), nearest=tuple(nearest))
