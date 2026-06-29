"""Remember/recall use-case over the Embedder + MemoryStore ports (ADR-0008).

``MemoryRecaller`` is a stateless function over the store, exactly like ``TurnEngine``:
every memory lives in ``MemoryStore``, so ``recall`` returns the same result before and
after a restart or model swap (the one hard rule). It never holds memory of its own.
"""

from collections.abc import Callable, Sequence
from uuid import uuid4

from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ports import Clock, Embedder, MemoryStore


def _uuid4_memory_id() -> str:
    """Default memory-id factory; injectable so tests can pin ids."""
    return str(uuid4())


class MemoryRecaller:
    """Embed-and-store on write, embed-and-search on read. This is the memory v1 use-case."""

    def __init__(
        self,
        store: MemoryStore,
        embedder: Embedder,
        clock: Clock,
        *,
        id_factory: Callable[[], str] = _uuid4_memory_id,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._clock = clock
        self._id_factory = id_factory

    async def record(self, text: str) -> MemoryRecord:
        """Embed ``text``, persist it as a ``MemoryRecord``, and return that record."""
        embedding = tuple(await self._embedder.embed(text))
        record = MemoryRecord(
            id=self._id_factory(), text=text, embedding=embedding, at=self._clock.now()
        )
        await self._store.add(record)
        return record

    async def recall(self, query: str, *, k: int) -> Sequence[ScoredMemory]:
        """Return the ``k`` memories most similar to ``query`` (most-similar first)."""
        embedding = await self._embedder.embed(query)
        return await self._store.search(embedding, k=k)
