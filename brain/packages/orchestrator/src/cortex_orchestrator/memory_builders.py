"""Memory wiring: the recaller, its scope policy, and its recall reranking policy (ADR-0008)."""

from collections.abc import Awaitable, Callable

import httpx

from cortex_core import (
    RAW_RECALL_POLICY,
    Clock,
    GlobalMemoryScope,
    MemoryRecaller,
    MemoryScope,
    MmrRecallPolicy,
    RecallPolicy,
    RecencyMmrRecallPolicy,
    RerankingRecallPolicy,
    SessionMemoryScope,
)
from cortex_embedding import LlamaCppEmbedder
from cortex_memory import PgVectorMemoryStore
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import MemoryConfig, MemoryScopeName

# An embedding is a quick request (no streaming), so it gets a finite overall timeout.
_EMBEDDER_TIMEOUT_S = 30.0
# The recency half-life is authored in days at the config seam and converted here (the core's
# ``RerankingRecallPolicy`` is unit-agnostic and takes seconds).
_SECONDS_PER_DAY = 86400.0


def memory_scope_from_name(name: MemoryScopeName) -> MemoryScope:
    """Map ``CORTEX_MEMORY_SCOPE`` to its recall-namespace policy (ADR-0008 scoping addendum)."""
    if name == "session":
        return SessionMemoryScope()
    return GlobalMemoryScope()


def recall_policy_from_config(config: MemoryConfig) -> RecallPolicy:
    """Map ``CORTEX_MEMORY_RECALL`` to its recall reranking policy (ADR-0008 rerank addendum)."""
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


async def build_memory(
    config: MemoryConfig, clock: Clock
) -> tuple[MemoryRecaller | None, Callable[[], Awaitable[None]]]:
    """Pick the memory backend from config; return the recaller (or None) with its closer."""
    if config.backend == "pgvector":
        client = httpx.AsyncClient(timeout=httpx.Timeout(_EMBEDDER_TIMEOUT_S))
        embedder = LlamaCppEmbedder(client, config.embedder_endpoint, model=config.embedder_model)
        store = await PgVectorMemoryStore.connect(config.dsn)

        async def close_memory() -> None:
            await store.aclose()
            await client.aclose()

        scope = memory_scope_from_name(config.scope)
        policy = recall_policy_from_config(config)
        return MemoryRecaller(store, embedder, clock, scope=scope, policy=policy), close_memory
    return None, noop_aclose
