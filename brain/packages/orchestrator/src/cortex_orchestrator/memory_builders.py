"""Memory wiring: the recaller, its scope policy, and its recall reranking policy."""

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

type RecallerFor = Callable[[InferenceBackend, str], MemoryRecaller]

_EMBEDDER_TIMEOUT_S = 30.0
_SECONDS_PER_DAY = 86400.0


def memory_scope_from_name(name: MemoryScopeName) -> MemoryScope:
    """Map ``CORTEX_MEMORY_SCOPE`` to its recall-namespace policy."""
    if name == "session":
        return SessionMemoryScope()
    return GlobalMemoryScope()


def recall_policy_from_config(
    config: MemoryConfig, backend: InferenceBackend, model: str
) -> RecallPolicy:
    """Map ``CORTEX_MEMORY_RECALL`` to its recall reranking policy, whose judge asks ``model``."""
    if config.recall == "judge":
        return JudgeRecallPolicy(backend, model, pool_factor=config.recall_pool_factor)
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
    """Map ``CORTEX_MEMORY_RECALL_AUDIT`` to the recall trail, or to no trail."""
    return LoggingRecallSink() if config.recall_audit else None


async def build_memory(
    config: MemoryConfig, clock: Clock
) -> tuple[RecallerFor | None, SessionMemoryCascade | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config: a recaller per model, the cascade, and a closer."""
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        scope = memory_scope_from_name(config.scope)
        audit = recall_audit_from_config(config)

        def recaller_for(backend: InferenceBackend, model: str) -> MemoryRecaller:
            policy = recall_policy_from_config(config, backend, model)
            return MemoryRecaller(store, embedder, clock, scope=scope, policy=policy, audit=audit)

        return recaller_for, SessionMemoryCascade(store, scope), close_memory
    return None, None, noop_aclose
