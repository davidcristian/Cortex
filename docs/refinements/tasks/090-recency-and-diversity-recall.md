# Recency-and-diversity recall policy

**Status:** landed 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The MMR addendum's deferred diversity-over-recency policy:
a fourth pure-core `RecencyMmrRecallPolicy` (`rerank.py`, behind the **unchanged
`MemoryStore`/`Embedder` ports**) runs the MMR greedy selection over the reranker's recency-blended
relevance instead of the raw cosine, so a hit is kept for being recent, relevant, and non-redundant
at once (neither the reranker nor plain MMR gives all three). The shared
`_recency_blend`/`_redundancy`/`_greedy_mmr` machinery was extracted from the existing two policies
(their behavior byte-for-byte unchanged) so the fourth is a composition, not a paste.
`CORTEX_MEMORY_RECALL=recency_mmr` selects it (now `raw`, `reranked`, `mmr`, or `recency_mmr`),
reusing the existing recency and MMR-lambda knobs; the reported `ScoredMemory.score` stays the raw
cosine, only order and membership change. CI-gated end to end over the fakes at 100%; no SQL change,
so no host validation is owed. Still open: the **model-based reranker** (which needs the sync
`RecallPolicy.select` to become async first, see the rerank entry above) and **surfacing the
blended relevance**, which is behind the unchanged seam. The opt-in policies and their shared math were split into
`rerank_policies.py` (the port and the default `RawRecallPolicy` stay in `rerank.py`) at the
300-line cap as this landed.

## Trail

- 2026-07-13: Recorded at the [ADR-0008 recency-and-diversity
  addendum](../../adr/ADR-0008-memory-v1.md).
