# Recency-and-diversity recall policy

**Status:** done 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The diversity-over-recency policy the MMR entry ([R-089](089-mmr-diversity-policy.md)) deferred.
A fourth pure-core `RecencyMmrRecallPolicy` in `rerank.py`, behind unchanged `MemoryStore` and
`Embedder` ports, runs the MMR greedy selection over the reranker's recency-blended relevance
instead of over the raw cosine, so a hit is kept for being recent, relevant and non-redundant at
once. Neither the reranker nor plain MMR gives all three.

The shared `_recency_blend`, `_redundancy` and `_greedy_mmr` helpers were extracted from the
existing two policies, whose behaviour did not change, so the fourth policy is a composition
rather than a copy. `CORTEX_MEMORY_RECALL=recency_mmr` selects it, so the choices are now `raw`,
`reranked`, `mmr` and `recency_mmr`, and it reuses the existing recency and MMR-lambda settings.
The reported `ScoredMemory.score` stays the raw cosine; only order and membership change. Covered
end to end in CI over the fakes at 100%; no SQL changed, so no host testing was needed.

The opt-in policies and their shared maths moved to `rerank_policies.py` at the 300-line cap; the
port and the default `RawRecallPolicy` stay in `rerank.py`.

Two refinements stay open behind the unchanged port: the model-based reranker
([R-092](092-model-based-reranker.md)), which needs `RecallPolicy.select` to become async first,
and reporting the blended relevance as its own field
([R-091](091-blended-relevance-field.md)).

## History

- 2026-07-13: Recorded at [ADR-0008 decision 10](../../adr/ADR-0008-memory-v1.md).
