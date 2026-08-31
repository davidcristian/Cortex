"""Remember/recall use-case over the Embedder + MemoryStore ports (ADR-0008)."""

from collections.abc import Callable, Sequence
from uuid import uuid4

from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ports import Clock, Embedder, MemoryStore, RecallAuditSink
from cortex_core.ranking import RecallAudit, dropped_candidates
from cortex_core.rerank import RAW_RECALL_POLICY, RecallPolicy
from cortex_core.scope import GLOBAL_MEMORY_SCOPE, MemoryScope


def _uuid4_memory_id() -> str:
    """Default memory-id factory; injectable so tests can pin ids."""
    return str(uuid4())


class MemoryRecaller:
    """Embed-and-store on write, embed-and-search on read. This is the memory use-case."""

    def __init__(  # noqa: PLR0913 -- four optional policy seams, each independently swappable
        self,
        store: MemoryStore,
        embedder: Embedder,
        clock: Clock,
        *,
        scope: MemoryScope = GLOBAL_MEMORY_SCOPE,
        policy: RecallPolicy = RAW_RECALL_POLICY,
        audit: RecallAuditSink | None = None,
        id_factory: Callable[[], str] = _uuid4_memory_id,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._clock = clock
        self._scope = scope
        self._policy = policy
        self._audit = audit
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
        scopes = self._scope.read_scopes(session_id)
        pool = await self._store.search(embedding, k=self._policy.candidate_k(k), scopes=scopes)
        available = await self._count_candidates(scopes)
        now = self._clock.now()
        ranking = await self._policy.select(pool, query=query, now=now, k=k, session_id=session_id)
        if self._audit is not None:
            await self._audit.record(
                RecallAudit(
                    session_id=session_id,
                    query=query,
                    pool_size=len(pool),
                    available=available,
                    k=k,
                    ranking=ranking,
                    dropped=dropped_candidates(pool, ranking),
                    at=now,
                )
            )
        return ranking.memories

    async def _count_candidates(self, scopes: Sequence[str] | None) -> int:
        """How many memories the read scopes hold, or ``0`` when no audit sink is wired."""
        if self._audit is None:
            return 0
        return await self._store.count_candidates(scopes=scopes)
