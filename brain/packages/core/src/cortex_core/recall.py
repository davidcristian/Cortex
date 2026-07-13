"""Remember/recall use-case over the Embedder + MemoryStore ports (ADR-0008)."""

from collections.abc import Callable, Sequence
from uuid import uuid4

from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ports import Clock, Embedder, MemoryStore
from cortex_core.rerank import RAW_RECALL_POLICY, RecallPolicy
from cortex_core.scope import GLOBAL_MEMORY_SCOPE, MemoryScope


def _uuid4_memory_id() -> str:
    """Default memory-id factory; injectable so tests can pin ids."""
    return str(uuid4())


class MemoryRecaller:
    """Embed-and-store on write, embed-and-search on read. This is the memory use-case."""

    def __init__(
        self,
        store: MemoryStore,
        embedder: Embedder,
        clock: Clock,
        *,
        scope: MemoryScope = GLOBAL_MEMORY_SCOPE,
        policy: RecallPolicy = RAW_RECALL_POLICY,
        id_factory: Callable[[], str] = _uuid4_memory_id,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._clock = clock
        self._scope = scope
        self._policy = policy
        self._id_factory = id_factory

    async def record(self, text: str, *, session_id: str, tainted: bool = False) -> MemoryRecord:
        """Embed ``text``, persist it in the turn's write-scope, and return the record."""
        embedding = tuple(await self._embedder.embed(text))
        record = MemoryRecord(
            id=self._id_factory(),
            text=text,
            embedding=embedding,
            at=self._clock.now(),
            scope=self._scope.write_scope(session_id),
            tainted=tainted,
        )
        await self._store.add(record)
        return record

    async def recall(self, query: str, *, k: int, session_id: str) -> Sequence[ScoredMemory]:
        """Return the ``k`` most relevant memories to ``query`` within the turn's read-scopes."""
        embedding = await self._embedder.embed(query)
        pool = await self._store.search(
            embedding, k=self._policy.candidate_k(k), scopes=self._scope.read_scopes(session_id)
        )
        return self._policy.select(pool, now=self._clock.now(), k=k)
