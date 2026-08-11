# Recency-weighted reranking and near-duplicate dedup

**Status:** landed 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

v1 recall was raw top-k cosine with no reranking,
recency weighting, or dedup. A new pure-core `RecallPolicy` seam (`rerank.py`, the
`MemoryScope`/`HistoryWindow` pattern) now turns an over-fetched candidate pool into the final
`k` hits behind the **unchanged `MemoryStore` port** (it needs the recaller's `Clock`, which the
store lacks, and composes recency with dedup in one pass the pgvector `ORDER BY <=> LIMIT`
cannot). `RawRecallPolicy` (the default singleton `RAW_RECALL_POLICY`) is v1 behavior exactly, so
recall stays byte-for-byte unchanged unless a deployment opts into `RerankingRecallPolicy`
(`CORTEX_MEMORY_RECALL=reranked`), which blends similarity with an exponential recency decay
(over an age floored at 0, so clock skew neither outranks a fresh hit nor overflows) and greedily
drops near-duplicate memories, tuned by the
`CORTEX_MEMORY_RECALL_*` knobs; the reported `ScoredMemory.score` stays the raw cosine, only order
and membership change. The `MemoryRecaller` over-fetches `policy.candidate_k(k)` then applies
`policy.select(now, k)`; the memory builders split to `memory_builders.py` for the line cap.
CI-gated end to end over the fakes at 100%; no SQL change, so no host validation is owed. Remaining
in the same area (ADR-0008 rerank addendum): a **model-based reranker** (a cross-encoder or an
LLM-judge `select`) and **surfacing the blended relevance** as a distinct field. **Cost
correction:** only the second is behind the unchanged seam. `RecallPolicy.select` is **sync**,
so a policy that calls a model does not fit it; like the history-summarization entry (see
[session-history.md](../index.md#session-history)), the port must go async first, and it inherits the
same non-reentrant GPU-lease hazard when the reranker runs inside a turn that already holds the
lease.
