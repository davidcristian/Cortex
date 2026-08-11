# Maximal-marginal-relevance diversity policy

**Status:** landed 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The rerank addendum's deferred diversity policy: a third
pure-core `MmrRecallPolicy` (`rerank.py`, behind the **unchanged `MemoryStore`/`Embedder` ports**)
builds its result greedily, each step keeping the candidate that maximizes
`relevance_weight * similarity - (1 - relevance_weight) * redundancy` (redundancy = its greatest
embedding cosine to an already-kept hit), so distinct-but-redundant memories sitting *below* the
reranker's near-duplicate cutoff still spread across the query's neighborhood instead of clustering
on its single closest region. `CORTEX_MEMORY_RECALL=mmr` selects it (now `raw`, `reranked`, or
`mmr`), `CORTEX_MEMORY_RECALL_MMR_LAMBDA` (0.5) is the relevance-vs-diversity dial (`1` pure
relevance, degenerating to `RawRecallPolicy` order; `0` pure diversity), reusing the shared
`recall_pool_factor`; the reported `ScoredMemory.score` stays the raw cosine, only order and
membership change. CI-gated end to end over the fakes at 100%; no SQL change, so no host validation
is owed. Still open: the **model-based reranker** (blocked on the sync `RecallPolicy.select`, see
above) and **surfacing the blended relevance**, behind the unchanged seam (the
**recency-and-diversity** policy it also named landed, the entry below).

## Trail

- 2026-07-13: Recorded at the [ADR-0008 MMR addendum](../../adr/ADR-0008-memory-v1.md).
