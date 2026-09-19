# Maximal-marginal-relevance diversity policy

**Status:** done 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The diversity policy the rerank entry ([R-088](088-recency-rerank-dedup.md)) deferred. A third
pure-core `MmrRecallPolicy` in `rerank.py`, behind unchanged `MemoryStore` and `Embedder` ports,
builds its result greedily: at each step it keeps the candidate with the highest
`relevance_weight * similarity - (1 - relevance_weight) * redundancy`, where redundancy is that
candidate's greatest embedding cosine to an already-kept hit. Memories that are distinct but
still similar, and so sit below the reranker's near-duplicate cutoff, then spread across the
query's neighbourhood instead of clustering on its closest region.

`CORTEX_MEMORY_RECALL=mmr` selects it, so the choices are now `raw`, `reranked` and `mmr`.
`CORTEX_MEMORY_RECALL_MMR_LAMBDA` (0.5) trades relevance against diversity: `1` is pure
relevance, which reduces to `RawRecallPolicy` order, and `0` is pure diversity. It reuses the
shared `recall_pool_factor`. The reported `ScoredMemory.score` stays the raw cosine; only order
and membership change. Covered end to end in CI over the fakes at 100%; no SQL changed, so no
host testing was needed.

Two refinements stay open behind the unchanged port: the model-based reranker
([R-092](092-model-based-reranker.md)), which is blocked on the synchronous
`RecallPolicy.select`, and reporting the blended relevance as its own field
([R-091](091-blended-relevance-field.md)). The recency-and-diversity policy this entry also named
shipped as [R-090](090-recency-and-diversity-recall.md).

## History

- 2026-07-13: Recorded at [ADR-0008 decision 10](../../adr/ADR-0008-memory-v1.md).
