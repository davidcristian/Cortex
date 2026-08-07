"""Remember/recall use-case over the Embedder + MemoryStore ports (ADR-0008).

``MemoryRecaller`` is a stateless function over the store, exactly like ``TurnEngine``:
every memory lives in ``MemoryStore``, so ``recall`` returns the same result before and
after a restart or model swap (the one hard rule). It never holds memory of its own.
"""

from collections.abc import Callable, Sequence
from uuid import uuid4

from cortex_core.memory import MemoryRecord, ScoredMemory
from cortex_core.ports import Clock, Embedder, MemoryStore, RecallAuditSink
from cortex_core.ranking import RecallAudit
from cortex_core.rerank import RAW_RECALL_POLICY, RecallPolicy
from cortex_core.scope import GLOBAL_MEMORY_SCOPE, MemoryScope


def _uuid4_memory_id() -> str:
    """Default memory-id factory; injectable so tests can pin ids."""
    return str(uuid4())


class MemoryRecaller:
    """Embed-and-store on write, embed-and-search on read. This is the memory use-case.

    The injected ``MemoryScope`` decides which namespace each turn records under and recalls
    from (ADR-0008 scoping addendum); the default ``GlobalMemoryScope`` keeps the one-global-
    space v1 behavior, so recall stays cross-session unless a deployment opts into scoping. The
    injected ``RecallPolicy`` reranks and prunes the recalled pool (ADR-0008 rerank addendum); the
    default ``RAW_RECALL_POLICY`` keeps v1 top-k cosine exactly, so recall is unchanged unless a
    deployment opts into reranking. The optional ``RecallAuditSink`` (ADR-0038) receives one
    ``RecallAudit`` per recall, carrying the ranking the policy returned; ``None`` (the default)
    is the founding silent recall path.
    """

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
        """Embed ``text``, persist it in the turn's write-scope, and return the record.

        ``tainted`` stamps the untrusted-provenance marker (ADR-0019). The caller passes the
        turn's taint state; a tainted memory is fenced on recall. Defaults ``False``, the trusted
        record an untainted turn writes.
        """
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
        """Return the ``k`` most relevant memories to ``query`` within the turn's read-scopes.

        The store returns a candidate pool sized by the ``RecallPolicy`` (``candidate_k``); the
        policy then reranks and prunes it to ``k``. The default policy fetches exactly ``k`` and
        keeps the store's similarity order, so recall is v1 top-k cosine unless reranking is on.

        The policy returns a ``Ranking`` (its keys and their basis, ADR-0038) and this method
        unwraps it: turn assembly wants hits, and widening this return would push a ranking through
        turn context and the seam for no consumer. The ranking instead goes to the ``audit`` sink
        when one is wired, which is where "why did recall return these?" is answerable.

        **An empty ranking is an answer and is returned as one.** A policy may keep nothing, either
        because the store held nothing or because the model read the pool and declined it (the
        ``DEMUR`` basis, ADR-0038 abstention addendum), and this method neither re-runs the search
        nor substitutes the pool: it returns no hits and the turn is assembled without a memory
        block. The audit is written for an empty ranking exactly as for a full one, so the trail
        distinguishes a considered refusal from an empty store by the basis it carries.
        """
        embedding = await self._embedder.embed(query)
        pool = await self._store.search(
            embedding, k=self._policy.candidate_k(k), scopes=self._scope.read_scopes(session_id)
        )
        now = self._clock.now()
        ranking = await self._policy.select(pool, query=query, now=now, k=k)
        if self._audit is not None:
            await self._audit.record(
                RecallAudit(
                    session_id=session_id,
                    query=query,
                    pool_size=len(pool),
                    k=k,
                    ranking=ranking,
                    at=now,
                )
            )
        return ranking.memories
