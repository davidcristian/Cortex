"""Memory wiring: the recaller, its scope policy, and its recall reranking policy (ADR-0008).

Split from `builders.py` when the recall reranking policy arrived (the 300-line cap); the contract
is the same. Builders are called only by `wiring.run_from_env`, each returning the dependency plus
the coroutine that releases it.

Memory is disabled by default (CI and the no-GPU dev loop run DB-free). With
`CORTEX_MEMORY_BACKEND=pgvector` the turn gets a `MemoryRecaller` over the `PgVectorMemoryStore` +
`LlamaCppEmbedder`, wired with two pure-core policies chosen here from env: the `MemoryScope`
(`CORTEX_MEMORY_SCOPE`, ADR-0008 scoping addendum) that decides which namespace a turn writes to and
reads from, and the `RecallPolicy` (`CORTEX_MEMORY_RECALL`, ADR-0008 rerank addendum) that reranks
and prunes the recalled pool. Scoping still defaults to the founding one-global-space behavior;
ranking no longer does, `judge` being the default since the turn-cost addendum measured it, so a
recalling turn asks the resident model which notes help and `CORTEX_MEMORY_RECALL=raw` is what
puts v1 top-k cosine back. The core never reads env; these two functions are its only
scoping/rerank seam.
"""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    RAW_RECALL_POLICY,
    Clock,
    GlobalMemoryScope,
    InferenceBackend,
    JudgeRecallPolicy,
    MemoryRecaller,
    MemoryScope,
    MmrRecallPolicy,
    RecallAuditSink,
    RecallPolicy,
    RecencyMmrRecallPolicy,
    RerankingRecallPolicy,
    SessionMemoryCascade,
    SessionMemoryScope,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_memory import LoggingRecallSink, PgVectorMemoryStore
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import MemoryConfig, MemoryScopeName

# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0
# The recency half-life is authored in days at the config seam and converted here (the core's
# ``RerankingRecallPolicy`` is unit-agnostic and takes seconds).
_SECONDS_PER_DAY = 86400.0


def memory_scope_from_name(name: MemoryScopeName) -> MemoryScope:
    """Map ``CORTEX_MEMORY_SCOPE`` to its recall-namespace policy (ADR-0008 scoping addendum).

    ``global`` keeps the founding one-global-space recall (spans conversations); ``session``
    isolates each conversation's memory to itself. The composition root's one env->core seam
    for scoping, since the core never reads the string.
    """
    if name == "session":
        return SessionMemoryScope()
    return GlobalMemoryScope()


def recall_policy_from_config(
    config: MemoryConfig, backend: InferenceBackend, cortex_model: str
) -> RecallPolicy:
    """Map ``CORTEX_MEMORY_RECALL`` to its recall reranking policy (ADR-0008 rerank addendum).

    ``raw`` keeps v1 top-k cosine exactly; ``reranked`` blends similarity with a
    recency decay and drops near-duplicates; ``mmr`` selects for maximal marginal relevance
    (query-relevance traded against diversity); ``recency_mmr`` runs that MMR selection over the
    recency blend, combining both axes; ``judge`` hands the pool to the resident model on the given
    ``backend`` and ranks by what it answers (ADR-0038), falling back to ``raw`` whenever the model
    cannot be reached or believed, and is **the default** since the turn-cost addendum measured
    what it does to a whole turn. Each is tuned by the ``CORTEX_MEMORY_RECALL_*`` knobs (each
    policy validates the ranges of the ones it uses). The composition root's one env->core seam for
    reranking, since the core never reads the string.
    """
    if config.recall == "judge":
        return JudgeRecallPolicy(backend, cortex_model, pool_factor=config.recall_pool_factor)
    if config.recall == "reranked":
        return RerankingRecallPolicy(
            half_life_seconds=config.recall_half_life_days * _SECONDS_PER_DAY,
            recency_weight=config.recall_recency_weight,
            dedup_threshold=config.recall_dedup_threshold,
            pool_factor=config.recall_pool_factor,
        )
    if config.recall == "mmr":
        return MmrRecallPolicy(
            relevance_weight=config.recall_mmr_lambda,
            pool_factor=config.recall_pool_factor,
        )
    if config.recall == "recency_mmr":
        return RecencyMmrRecallPolicy(
            half_life_seconds=config.recall_half_life_days * _SECONDS_PER_DAY,
            recency_weight=config.recall_recency_weight,
            relevance_weight=config.recall_mmr_lambda,
            pool_factor=config.recall_pool_factor,
        )
    return RAW_RECALL_POLICY


def recall_audit_from_config(config: MemoryConfig) -> RecallAuditSink | None:
    """Map ``CORTEX_MEMORY_RECALL_AUDIT`` to the recall trail, or to no trail (ADR-0038).

    ``True`` attaches ``LoggingRecallSink``, one structured line per recall carrying the pool, the
    rank basis and each kept hit's key, never any text; ``False`` (the default) is the founding
    silent recall path, where the recaller has no sink at all rather than a sink that drops.
    """
    return LoggingRecallSink() if config.recall_audit else None


async def build_memory(
    config: MemoryConfig, clock: Clock, backend: InferenceBackend, cortex_model: str
) -> tuple[MemoryRecaller | None, SessionMemoryCascade | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config; return the recaller, the delete cascade, and a closer.

    ``none`` disables memory (both are None). The DB-less default CI and the no-GPU dev loop run.
    ``pgvector`` connects an asyncpg pool and a CPU embedder client; the returned closer releases
    both. The ``scope`` config selects the recaller's namespace policy (default global, ADR-0008
    addendum) and ``recall`` its reranking policy (default raw top-k cosine, ADR-0008 rerank
    addendum), which is why the inference ``backend`` and the cortex model id reach here: the
    model-based rank is a policy over that port (ADR-0038). ``recall_audit`` attaches the structured
    recall trail. The ``SessionMemoryCascade`` shares that store and scope but exposes only the
    scope-guarded session-delete forget (ADR-0021), the trusted out-of-band path the turn-facing
    recaller must never carry; the server wires it into ``DeleteSession``, never into an engine.
    """
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        scope = memory_scope_from_name(config.scope)
        policy = recall_policy_from_config(config, backend, cortex_model)
        audit = recall_audit_from_config(config)
        recaller = MemoryRecaller(store, embedder, clock, scope=scope, policy=policy, audit=audit)
        return recaller, SessionMemoryCascade(store, scope), close_memory
    return None, None, noop_aclose
