# Memory

Deferred refinements from the Slice 5 memory work under [ADR-0008](../adr/ADR-0008-memory-v1.md): the memory store, its scoping seam, and the pure-core recall policies. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** session+global union read policy, per-scope retention/eviction, cross-scope recall ranking, tiered / self-editing memory + summarization, model-based reranker, write-salience policy, recall observability, ANN index

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
  **The delete/forget verb landed 2026-07-16 ([ADR-0008 delete-scope
  addendum](../adr/ADR-0008-memory-v1.md)); the policies stay deferred.**
  `MemoryStore.delete_scope(scope) -> int` hard-deletes one namespace and returns the row count, the
  one verb of the several this entry named that has recorded consumers already waiting on it: a
  **session-delete cascade** (which could not honestly delete a session's derived memories,
  [session-read-seam.md](session-read-seam.md)) and **per-scope eviction**. It is by-scope, not
  by-id, because the only link from a session to its memories is the `scope` (`SessionMemoryScope`
  writes `scope == session_id`), and it takes a single required scope with no wildcard so a namespace
  is dropped only when named (a caller mapping a session to `GLOBAL_SCOPE` under global scoping must
  never pass it). Port + contract test + fake + pgvector adapter, CI-gated at 100%, the real DELETE
  host-validated against pgvector (rows 3 to 0, count 3, other scopes spared, a no-match scope
  returns 0). Data-loss-safe by construction: memory is not a tool in any registry, and the
  `MemoryRecaller` a turn is handed exposes only record/recall, so no tool call, tainted or not, can
  spell "forget everything" (a structural test pins that surface). **Still deferred, each for want of
  a consumer and not a missing verb now:** self-editing (**update** in place), **tiered**
  promote/demote/expire, **write-salience** (its own entry below), and the **per-scope retention
  _policy_** (the eviction verb exists; a retention scheduler deciding what to evict when does not,
  and nothing drives one). **Per-provenance eviction** ([untrusted-content.md](untrusted-content.md))
  wants a different filter, since a memory record stores only the `tainted` bit, not the ADR-0027
  structured provenance, so `delete_scope` does not serve it and it stays fix-when-it-bites.
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
- **Surfacing the blended relevance as a distinct field closed 2026-07-16 as declined, no consumer
  ([ADR-0008 relevance-field addendum](../adr/ADR-0008-memory-v1.md)).** The three rerank entries
  above each carried it as the one reranker deferral behind the unchanged seam. That is true of its
  *cost* and had been read as readiness; two findings closed it instead. **Nothing reads a recall
  score.** `ScoredMemory.score` is written by both store adapters and consumed only by the policies
  themselves (as an input) and by tests. The single production consumer of a recall result,
  `TurnEngine._render_memory_context` (`engine.py`), reads `record.text`, `record.tainted`, and
  `record.id`, and never touches `score`. The seam carries no memory at all (`proto/body.proto` has
  no memory message), the recall path has no logging and no audit sink, and the origin addendum
  itself conditioned the entry on "should a consumer ever need to display it". **And there is no
  single blend to surface.** The opt-in policies rank by three different quantities:
  `RerankingRecallPolicy` by the recency blend (comparable across hits), while `MmrRecallPolicy` and
  `RecencyMmrRecallPolicy` rank by an MMR objective computed against the kept set at pick time,
  which is order-dependent and therefore not comparable between hits in one result. **Cost
  correction:** the "unchanged seam" reading holds only for the design the addendum warns against,
  adding the field to `ScoredMemory` itself, the store's own output type, which would then have to
  carry a blend no store computes. Keeping the two quantities distinct means widening
  `RecallPolicy.select`'s return, the same signature the model-based reranker is blocked on widening
  to async, so a consumer should reopen both at once rather than change `select` twice. Verified
  live against pgvector: the adapter reports cosine similarity (a probe row at distance 0.0002 came
  back as score 0.9998), and under `reranked` the emitted order was scores 0.6000, 0.9998, 0.7071,
  which the reported field does not explain while the blend (0.7131, 0.6999, 0.5700) does. What the
  close keeps instead is the invariant, stated on the type a reader actually opens: `ScoredMemory`
  now documents that its score is the store's raw cosine and never a policy's rank key, which is
  what stops the two quantities being confused in the meantime. **Reopens** the first time
  a surface displays or logs a recall hit's ranking, and it is then a `select` change, not a field.
- **The model-based reranker, audited 2026-07-16 and kept deferred with the blocker sharpened
  ([ADR-0008 reranker-audit addendum](../adr/ADR-0008-memory-v1.md)).** The rerank, MMR, and
  recency-and-diversity entries above each keep it deferred behind the sync `RecallPolicy.select`
  and the shared GPU-lease hazard. Audited against the code, the first cost is bounded and the second
  is misframed, but it stays deferred, alongside the summarization half it shares a design with (see
  [session-history.md](session-history.md)). **The async widening is clean and contained.**
  `RecallPolicy.select` has one production caller, `MemoryRecaller.recall` (`recall.py`), already
  `async`, so widening to `async` adds one `await` and cascades no colour upward; the implementers are
  `RawRecallPolicy` plus the three opt-in policies, and none calls another's `select` (they compose
  via the shared `_greedy_mmr`/`_recency_blend` helpers), so no implementer infects another. An
  `async def select` with a synchronous body is gate-clean (`unused-async` is preview-only, off here).
  **The lease hazard is navigable, and this entry's framing overstated it.** Recall runs inside
  `_inference_messages`, which `handle_turn` awaits to completion before the reply stream acquires the
  resident model's non-reentrant lock (`model.py`; held across the whole stream in `backend.py`), so
  at reranking time the turn does not yet hold the lease. A reranker that fully drains its model call
  is a sequential acquire, the title generator's discipline, proven safe against the real manager (a
  drained acquire then the reply's acquire succeeds; a call held open across it deadlocks). So "runs
  inside a turn that already holds the lease" is imprecise: the real hazard is an abandoned reranker
  stream, not nesting. **Why it still waits.** Beyond a model reranker's ordering being unverifiable
  on the 8 GB dev GPU (the cortex tier does not fit), the declined blended-relevance field and the
  recall-observability entry both resolve to a `RecallPolicy.select` widening, and the recorded
  guidance is to change `select` once for all three consumers (a model rank, the distinct blended
  field, an observability sink reading the rank key) rather than twice; an async-only widening now
  would be the first of two changes. So this reopens with the model manager's real GPU lifecycle,
  landing the async widening, the richer `select` return, and the model policy as one design.
- **Write-salience policy.** v1 records the raw exchange text every turn; deciding what
  *deserves* remembering (salience filtering at record time) is a later policy (ADR-0008 risks).
  Its summarization half is adjacent to the tiered-memory entry above. **Cost correction:** a
  policy that can decline to record does not fit the current shape, because
  `MemoryRecaller.record` returns a **non-optional** `MemoryRecord`; the return has to widen
  (or the decision move to the caller) before anything can drop a write.
- **Recall observability, opened 2026-07-16 by the blended-relevance close.** Answering "why did
  recall return these?" today means writing a throwaway script against the store, which is exactly
  what that close's live check had to do: the recall path emits nothing. The core has no logger at
  all, and the only observability port of this shape is `ToolAuditSink` (ADR-0009), which memory has
  no analog of, so this is a **new port plus a sink adapter**, not a field on `ScoredMemory`, and
  that is why it is not a cheap follow-on to the close that named it. It is also the consumer that
  would **reopen** the declined field: a sink recording a hit's rank key is the first code that
  reads one, and it should then arrive as a `RecallPolicy.select` widening rather than a second
  field on the store's own output type. **Fix when it bites:** the first time a real session recalls
  something visibly wrong and the ranking cannot be inspected after the fact.
- **ANN index.** Exact cosine now; an approximate index would need a migration, per
  [ADR-0004](../adr/ADR-0004-model-lineup.md).
