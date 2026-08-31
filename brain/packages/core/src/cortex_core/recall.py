"""Remember/recall use-case over the Embedder + MemoryStore ports (ADR-0008).

``MemoryRecaller`` is a stateless function over the store, exactly like ``TurnEngine``:
every memory lives in ``MemoryStore``, so ``recall`` returns the same result before and
after a restart or model swap (the one hard rule). It never holds memory of its own.
"""

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
    """Embed-and-store on write, embed-and-search on read. This is the memory use-case.

    The injected ``MemoryScope`` decides which namespace each turn records under and recalls
    from (ADR-0008 scoping addendum); the default ``GlobalMemoryScope`` keeps the one-global-
    space v1 behavior, so recall stays cross-session unless a deployment opts into scoping. The
    injected ``RecallPolicy`` reranks and prunes the recalled pool (ADR-0008 rerank addendum); this
    constructor's own default is ``RAW_RECALL_POLICY``, v1 top-k cosine exactly, which is a default
    for a caller that passes no policy and not what the brain ships (the composition root selects
    the model rank, ADR-0038 turn-cost addendum). The optional ``RecallAuditSink`` (ADR-0038)
    receives one ``RecallAudit`` per recall, carrying the ranking the policy returned; ``None``
    (the default) is the unaudited recall path this class started with.
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

        The policy is handed this recall's ``session_id`` as well, which is the only identity that
        crosses the port (ADR-0038 named-recall addendum): a policy that reports a degradation can
        then say which conversation it happened in, and the audit trail beside it is keyed the same
        way, so the two lines pair. Nothing is fetched to pass it; this method already held it.

        The policy returns a ``Ranking`` (its keys and their basis, ADR-0038) and this method
        unwraps it: turn assembly needs hits, and widening this return would push a ranking through
        turn context and the seam for no consumer. The ranking instead goes to the ``audit`` sink
        when one is wired, which is where "why did recall return these?" is answerable.

        The audit also carries what the rank dropped, since a pool the caller never sees is the
        other half of that question, and the whole record including that difference is assembled
        inside the ``audit is not None`` guard: a deployment with no sink wired walks the pool once
        for the policy and never again. The store's own count of the read scopes rides the same
        guard for the same reason (ADR-0038 candidate-count addendum), and it is what tells a pool
        that filled to its requested width from a store that held exactly that many.

        An empty ranking is an answer and is returned as one. A policy may keep nothing, either
        because the store held nothing or because the model read the pool and declined it (the
        ``DEMUR`` basis, ADR-0038 abstention addendum), and this method neither re-runs the search
        nor substitutes the pool: it returns no hits and the turn is assembled without a memory
        block. The audit is written for an empty ranking exactly as for a full one, so the trail
        tells a declined rank from an empty store by the basis it carries.
        """
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
        """How many memories the read scopes hold, or ``0`` when no audit sink is wired.

        Asked of the store rather than measured off the pool, which is the point: a length over
        returned rows would report the cutoff back to itself. Asked here, straight after the
        search rather than after the rank, because these are two reads and not one transaction,
        and a model rank sits between them for the best part of a second; adjacent statements are
        the closest two reads get to describing one moment. Asked only when a sink exists, so the
        unaudited path stays at exactly one store read and the ``0`` never reaches a line, the
        record being assembled under the same condition.
        """
        if self._audit is None:
            return 0
        return await self._store.count_candidates(scopes=scopes)
