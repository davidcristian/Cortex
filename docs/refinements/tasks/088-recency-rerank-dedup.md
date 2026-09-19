# Recency-weighted reranking and near-duplicate dedup

**Status:** done 2026-07-13
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

v1 recall was raw top-k cosine with no reranking, recency weighting or dedup. A pure-core
`RecallPolicy` port in `rerank.py` now turns an over-fetched candidate pool into the final `k`
hits, with no change to `MemoryStore`. It sits in the core because it needs the recaller's
`Clock`, which the store does not have, and because it combines recency with dedup in one pass
that the pgvector `ORDER BY <=> LIMIT` cannot do.

`RawRecallPolicy`, the default singleton `RAW_RECALL_POLICY`, is exactly v1 behaviour, so recall
is unchanged unless a deployment sets `CORTEX_MEMORY_RECALL=reranked`. `RerankingRecallPolicy`
combines similarity with an exponential recency decay over an age floored at 0, so clock skew
neither outranks a fresh hit nor overflows, and then greedily drops near-duplicate memories. The
`CORTEX_MEMORY_RECALL_*` settings tune it. The reported `ScoredMemory.score` stays the raw
cosine; only order and membership change.

`MemoryRecaller` over-fetches `policy.candidate_k(k)` and then applies `policy.select(now, k)`.
The memory builders moved to `memory_builders.py` for the line cap. Covered end to end in CI over
the fakes at 100%; no SQL changed, so no host testing was needed.

Two refinements stay open (ADR-0008 decision 10): a model-based reranker, a cross-encoder or an
LLM judge in `select` ([R-092](092-model-based-reranker.md)), and reporting the blended relevance
as its own field ([R-091](091-blended-relevance-field.md)). Only the second is behind an
unchanged port. `RecallPolicy.select` is synchronous, so a policy that calls a model does not fit
it; the port must become async first, and it then inherits the same non-reentrant GPU-lease
problem as history summarization ([session-history.md](../index.md#session-history)) when the
reranker runs inside a turn that already holds the lease.
