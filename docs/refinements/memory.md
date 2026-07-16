# Memory

Deferred refinements from the Slice 5 memory work under [ADR-0008](../adr/ADR-0008-memory-v1.md): the memory store, its scoping seam, and the pure-core recall policies. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** session+global union read policy, per-scope retention/eviction, cross-scope recall ranking, tiered / self-editing memory + summarization, model-based reranker, surfacing the blended relevance, write-salience policy, ANN index

**Memory in Slice 5 ([ADR-0008](../adr/ADR-0008-memory-v1.md)):**
- **Per-session / namespaced scoping landed 2026-07-06 ([ADR-0008 scoping addendum](../adr/ADR-0008-memory-v1.md)).**
  A `MemoryScope` policy seam (pure core, the `HistoryWindow` pattern) maps a turn's `session_id`
  to its write-scope and read-scopes; `MemoryRecord` gained an opaque `scope` and
  `MemoryStore.search` an optional `scopes` filter (`WHERE scope = ANY`, default `None` = the v1
  global space). `GlobalMemoryScope` (the default, keeping recall cross-session) and
  `SessionMemoryScope` (per-conversation isolation) ship, selected by `CORTEX_MEMORY_SCOPE`. CI-gated
  end to end over the fakes; the pgvector SQL host-validated via Docker. Remaining behind the same
  seams: a **session+global union** read policy (dead until something writes durable global facts
  under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.
- **Tiered / self-editing memory + summarization.** Letta's good ideas, adoptable later without
  the framework, per decision 1. **Cost correction:** not behind the unchanged port. `MemoryStore`
  is **`add` + `search` only**, so tiering (promote, demote, expire), self-editing (update in
  place), and any retention or eviction policy all need verbs the port does not have, plus the
  pgvector adapter and a fake to implement them. Per-scope retention and per-provenance eviction
  are blocked on the same missing verbs.
- **Recency-weighted reranking + near-duplicate dedup landed 2026-07-13 ([ADR-0008 rerank
  addendum](../adr/ADR-0008-memory-v1.md)).** v1 recall was raw top-k cosine with no reranking,
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
  [session-history.md](session-history.md)), the port must go async first, and it inherits the
  same non-reentrant GPU-lease hazard when the reranker runs inside a turn that already holds the
  lease.
- **Maximal-marginal-relevance diversity landed 2026-07-13 ([ADR-0008 MMR
  addendum](../adr/ADR-0008-memory-v1.md)).** The rerank addendum's deferred diversity policy: a third
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
- **Recency-and-diversity recall landed 2026-07-13 ([ADR-0008 recency-and-diversity
  addendum](../adr/ADR-0008-memory-v1.md)).** The MMR addendum's deferred diversity-over-recency policy:
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
- **Write-salience policy.** v1 records the raw exchange text every turn; deciding what
  *deserves* remembering (salience filtering at record time) is a later policy (ADR-0008 risks).
  Its summarization half is adjacent to the tiered-memory entry above. **Cost correction:** a
  policy that can decline to record does not fit the current shape, because
  `MemoryRecaller.record` returns a **non-optional** `MemoryRecord`; the return has to widen
  (or the decision move to the caller) before anything can drop a write.
- **ANN index.** Exact cosine now; an approximate index would need a migration, per
  [ADR-0004](../adr/ADR-0004-model-lineup.md).
