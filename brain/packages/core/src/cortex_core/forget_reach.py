"""Add the stored rows a request to forget reaches to the rows recall ranked for the turn."""

from collections.abc import Sequence

from cortex_core.forget_unnamed import asks_to_forget_keeping
from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.memory_request import asks_to_forget
from cortex_core.memory_values import whole_values
from cortex_core.recall import MemoryRecaller

# As many rows as recall ranks, so a forget turn shows at most twice the rows of another turn.
FORGET_REACH_LIMIT = 5


async def with_forget_reach(
    query: str, memory: MemoryRecaller, hits: Sequence[ScoredMemory], *, session_id: str
) -> Sequence[ScoredMemory]:
    """``hits``, then on a request to forget up to ``FORGET_REACH_LIMIT`` more rows it reaches:
    those holding a value ``query`` names, or the nearest when it names none beside a fact to keep.
    """
    keeping = asks_to_forget_keeping(query)
    if not keeping and not asks_to_forget(query):
        return hits
    values = whole_values(query)
    rows: list[MemoryRecord] = []
    for value in values:
        rows += await memory.find_value(value, session_id=session_id, limit=FORGET_REACH_LIMIT)
    if keeping and not values:
        rows += await memory.nearest(query, session_id=session_id, limit=FORGET_REACH_LIMIT)
    held = {hit.record.id for hit in hits}
    added = {row.id: row for row in rows if row.id not in held}
    reached = [ScoredMemory(record=row, score=0.0) for row in added.values()]
    return [*hits, *reached[:FORGET_REACH_LIMIT]]
