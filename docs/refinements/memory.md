# Memory

Deferred refinements from the Slice 5 memory work under [ADR-0008](../adr/ADR-0008-memory-v1.md): the memory store, its scoping seam, and the pure-core recall policies. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** 9 (session+global union read policy, per-scope retention/eviction, cross-scope recall ranking, tiered / self-editing memory + summarization, write-salience policy, ANN index, a cross-encoder rank, `MemoryStoreError` covering an outage and a malformed row alike, the `MemoryStore` check list's missing backend-failure check). **The count went 7 to 8 to 9 across 2026-08-11**, and both moves are written out because the first of them was made against a header that never recorded it. Filing the entry that a dead embedder or an unreachable Postgres fails the turn rather than costing it its notes took the area to 8, and it moved the index cell and not this line, which went on reading 7 for the hours the entry was open; the two now agree at 9. Closing that entry the same day took it back to 7 and **opened two in its place**, both of them residue of the close rather than anything found beside it: the adapter wraps a malformed row into the same `MemoryStoreError` an unreachable server raises, so the degradation the close installed swallows a data defect as if it were an outage, and the `MemoryStore` shared check list still has no backend-failure check where the `Embedder` list has one, which is why the store's twin gained a `fail_with` of its own rather than a check both implementations answer. The close itself came **ahead of a trigger neither arm of which fired**, no live turn having been taken against a stopped server and no other capability's degraded-mode question having reopened, and it was taken because the entry's only blocker was the decision it named. **The count fell from 8 to 7 on 2026-08-10 and nothing opened in its place**, when the question of why a memory was never a candidate closed **ahead of its trigger**, which is recorded here rather than smoothed over: neither arm of that trigger fired, no investigation having run and no pool having been widened, and the work was taken because the entry's only blocker was the trigger itself rather than a cost argument or an open question. `MemoryStore` gained `count_candidates`, so the trail now carries what the pool was drawn from beside what came back, and equal numbers are the line's way of saying the pool WAS the whole readable store. Two of that entry's own claims were tested against the tree and one failed: the requested width is not `k` times the pool factor under `raw` or on a fallback line, which costs no field, because the count makes the width redundant rather than merely inferable. What the close settled by measurement is that an exact count is the honest design and not the expensive one, an index-only `count(*)` being 2.0 ms against a 520 ms search while folding the total into the ranked select would have cost 2.85 times it. **The count held at 8 on 2026-08-09 because one closed and one opened in the same change**, written out here rather than left to arithmetic: auditing the candidates a rank dropped landed ahead of its trigger, because the default moved to `judge` underneath it and a judge keeps about one note where the cosine kept five, so the recall trail was thinnest exactly where most of the pool now disappears. What opened in its place is the question that close's own line raises next, why an id is in neither the kept nor the dropped list, and the third of it that no reader can derive from config is behind `MemoryStore.search`, which returns the top rows and reports no total. **The count fell from 9 to 8 later on 2026-08-08 and again nothing opened in its place**, when the geometric policies' missing refusal closed as **declined on measurement**: the entry's second trigger was a calibration run giving the floor a number, the run was done on the real embedder over this area's own corpus, and it found that no number exists, because the answerable and unanswerable populations overlap behind both embedding models the repo ships a path for. The two words that keep the area honest about it are that the mechanism was refuted rather than the goal abandoned: the shipped default still declines, it just does so by reading rather than by measuring distance. **The count fell from 10 to 9 earlier on 2026-08-08, and that one closed alone too**: the judge's default was the last entry here waiting on a decision rather than on work, the user asked for the end-to-end turn cost before calling it, the measurement came in at 0.515 s of time to first token against a control whose interval spans zero, and `CORTEX_MEMORY_RECALL` now ships as `judge`. Nothing opened in its place, the one thing it leaves behind being a caveat no run by this repo's author can retire. **The count held at 10 on 2026-08-07 because one item closed and one opened in the same change**, and it is written out here rather than left to arithmetic: the judge's abstention landed, and the close named what it does not reach, which is that the shipped geometric policies still hand a turn their nearest misses on a question memory cannot answer. **The tenth was added 2026-08-06 by the corpus widening, which found it; the two before it were added the same day, correcting a line and an index cell that had read 7.** The ranked-recall close did half of its own bookkeeping: it struck the model-based reranker and recall observability from this line when they landed, and it did not add the two deferrals the same close opened, which are written up at the end of the ranked-recall entry below and at [ADR-0038](../adr/ADR-0038-ranked-recall.md). A close that names what it opens and then leaves the header naming only what it shut loses an open item exactly as a count that fails to move does.

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
  stream, not nesting. **Why it still waits, and the hardware clause is struck (2026-07-19).** This
  read "a model reranker's ordering is unverifiable on the 8 GB dev GPU (the cortex tier does not
  fit)", which is false and was doing work here:
  [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) measured the real cortex plus its vision
  projector resident on that card at `-ngl 99 --ctx-size 4096 --parallel 1`, and
  [ADR-0030](../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
  8188 MiB, so a rank over a handful of candidates is judgeable agent-side today and only a 16K production context
  is out of reach. What binds is sequencing, and it always was: the declined blended-relevance field
  and the recall-observability entry both resolve to a `RecallPolicy.select` widening, and the
  recorded guidance is to change `select` once for all three consumers (a model rank, the distinct
  blended field, an observability sink reading the rank key) rather than twice; an async-only
  widening now would be the first of two changes. So this reopens when that widening is taken,
  landing the async change, the richer `select` return, and the model policy as one design.
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
- **The model-based reranker, the declined blended-relevance field, and recall observability all
  landed together 2026-08-06 ([ADR-0038](../adr/ADR-0038-ranked-recall.md)), which is what the
  audit above said they would have to do.** `RecallPolicy.select` was widened once, for all three:
  it is now `async def select(hits, *, query, now, k) -> Ranking`. **The blended-relevance decline
  is reversed**, and the reversal is about placement rather than verdict: the key a policy ranked by
  is `RankedMemory.key` on the policy's own return, never a second field on `ScoredMemory`, which
  keeps the store's score meaning the raw cosine exactly as that close insisted. The
  no-single-blend finding is answered rather than dodged by `RankBasis` (`ECHO`, `EMBER`, `SPREAD`,
  `SWEEP`, `VERDICT`), whose `comparable` property carries the close's own discovery that an MMR key
  is measured against the kept set and so means nothing beside another. **Recall observability** is
  the `RecallAuditSink` port plus `LoggingRecallSink` (`cortex_memory/audit.py`), one structured
  line per recall carrying the pool size, the basis, and each kept hit's id, score, key and taint
  bit, and deliberately no text at all, the tool audit's stance on result bytes applied to
  conversation content. `CORTEX_MEMORY_RECALL_AUDIT=1` turns it on. **The model rank** is
  `JudgeRecallPolicy` (`rerank_judge.py`, `CORTEX_MEMORY_RECALL=judge`), which sends the
  over-fetched pool to the resident cortex as a numbered list under a JSON-schema-constrained
  request and falls back to another policy on any failure to reach or believe it, the emitted basis
  then being the fallback's so the trail says what actually ranked. **Measured against the cosine
  that ships**, on ten notes and six questions worded so the answer shares no vocabulary with the
  question while a distractor shares plenty: mean reciprocal rank 0.917 to 1.000, the correct note
  placed first 5 of 6 times against 6 of 6, no fallbacks, and the judge returned *fewer* than `k`
  because it drops notes that do not help, which is a larger win in the turn's context than in the
  ranking. It costs a full cortex generation per recall, so the default stays `raw`. **Two claims of
  the audited entries did not hold.** Both name `_inference_messages` in `engine.py` as the caller,
  a method that no longer exists (it is `MemoryRecaller.recall` in `recall.py` for this port, still
  `async`, so the substance held); and neither noticed that **`select` did not carry the query**, so
  the widening was three changes rather than two, which is the one place their cost estimate was
  too small. Still open here: a **cross-encoder** rank, which is the other form of a model reranker
  and wants a scoring-model port rather than a chat completion, so it is a new adapter and not a
  policy (trigger: a measured shortfall of the judge on a real corpus, or a latency budget it
  cannot meet); and **auditing the candidates that were dropped**, which `RecallAudit` does not
  carry because a non-picked candidate's `SPREAD`/`SWEEP` key is not well defined (trigger: the
  first investigation that needs to know why a specific memory was *not* returned).
  **The dropped candidates landed 2026-08-09, ahead of that trigger and because the default moved
  under it** ([ADR-0038](../adr/ADR-0038-ranked-recall.md) dropped-candidate addendum). The entry
  was filed as fix-when-it-bites against a trail nobody was reading yet; what changed is that
  `CORTEX_MEMORY_RECALL` ships as `judge`, which is measured returning 1.17 notes where the cosine
  returned 5, so the recall trail was thinnest exactly where most of the pool now disappears.
  **The stated obstacle is real and answers itself.** There is no `SPREAD`/`SWEEP` key for a
  candidate that never joined a kept set, and there is no `VERDICT` key either, since the judge
  leaves an unhelpful note out of its order rather than scoring it low; under `ECHO` and `EMBER` a
  key could be computed after the fact, which is not the same as having one, a `Ranking` carrying
  keys for the hits it kept and for nothing else. What exists for every candidate under every basis
  is the store's own cosine, the store having produced the pool, so the close logs the id and that
  cosine and omits the key that does not apply. The line now carries
  `dropped`, one id and score per candidate the rank passed over, and `dropped_omitted`, so an id
  in neither `hits` nor `dropped` was never a candidate at all, which is the distinction an
  investigation actually arrives with and the one a pool *count* could never draw. **What it
  deliberately cannot say is why**: a rank has an opinion on record only about what it kept, so the
  trail is an account of what was available. **Bounded at 20**, the whole pool a default deployment
  fetches (`DEFAULT_RECALL_K` 5 at `pool_factor` 4), so a shipped line never truncates and the
  bound bites only on a wider over-fetch, where a line growing with the pool would make the trail
  the thing worth turning off; what it cuts is the tail of the store's own order and the count of
  what it cut rides the line. Text is absent structurally rather than by the sink's restraint,
  `DroppedCandidate` having no field that could hold any. Hexagonal placement is the core's
  `dropped_candidates(pool, ranking)` for the difference and the bound, the sink for the emission
  and nothing else. **Cost correction:** the entry priced nothing, and the shape it implied (a key
  per dropped candidate) does not exist; what shipped is two value types, one pure function, one
  required `RecallAudit` field and two log keys, all inside the existing `RecallAuditSink` port.
  The audit stays opt in and off still costs nothing, the whole record being assembled inside
  `MemoryRecaller.recall`'s `audit is not None` guard, which an instrumented pool counting its own
  walks pins at 1 unaudited against 2 audited rather than leaving to inspection. **Opens one**, the
  entry below: the line can now say a memory was never a candidate, and still cannot say why.
- **The trail cannot say why a memory was never a candidate, opened 2026-08-09 by the
  dropped-candidate close** ([ADR-0038](../adr/ADR-0038-ranked-recall.md) dropped-candidate
  addendum). That close draws the line between "was a candidate and was dropped" and "was not a
  candidate" and stops there, which is the whole of what its own entry asked for. The next question
  is why an id is in neither list, and three answers the line cannot separate: the memory ranked
  below the pool cutoff, its scope was not read, or it was never written. Two thirds of that is
  thinner than it looks, which is why this is filed small rather than as an observability gap. The
  scopes are fully determined by `CORTEX_MEMORY_SCOPE` and the `session` the line already carries
  (`GlobalMemoryScope` reads everything, `SessionMemoryScope` reads that one session), and the
  requested width is `k` times `CORTEX_MEMORY_RECALL_POOL_FACTOR`, so a reader holding the
  deployment's config derives both and logging them would be a convenience rather than new
  information. **What no reader can derive is the third that matters:** `pool_size` says how many
  candidates came back, never how many there were, so a pool filled to the requested width cannot
  be told from a store that held exactly that many, and a memory missing from a full line was
  either cut by the cutoff or absent from the store with nothing on the line saying which.
  **Cost correction ahead of time:** that half is *not* behind the unchanged port.
  `MemoryStore.search` returns the top rows and reports no total, so the number would have to come
  out of the store, meaning the port, both adapters, the fake, the contract test, and a count
  alongside the ranked select in the pgvector one. **Trigger:** the first investigation whose
  memory is not in the pool at all, or a deployment that has widened its pool and wants to know
  whether it is wide enough.
  **Landed 2026-08-10, and the trigger did not fire**
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) candidate-count addendum). Neither arm of it: no
  investigation has run and no pool has been widened. It was taken because the user asked for the
  backlog to be worked and this entry's only blocker was its trigger rather than a cost argument or
  an undecided question, and because the same thing that gave the close above its urgency gives
  this one its, the default having moved to `judge` and left the trail thinnest where most of the
  pool now disappears. That is written here rather than dressed up, a deferral taken ahead of its
  trigger being a decision like any other. **The cost correction was right and the shape survived
  the tree unchanged:** `MemoryStore.count_candidates(*, scopes=None) -> int` is a new verb rather
  than a widened `search`, so the one production caller of `search` is untouched and only the trail
  pays; the pgvector adapter runs `SELECT count(*)` under the same `WHERE scope = ANY` a scoped
  search applies, the in-memory twin counts the same filtered list it would have ranked, and
  `RecallAudit` carries a required `available` the sink spells out as one more key. The reading is
  a comparison rather than a number: equal to `pool_size` the pool WAS the whole readable store, so
  an id on neither `hits` nor `dropped` was never written or was written outside the read scopes;
  below it the pool was cut and an absent memory may only have ranked under the cutoff. **One of
  this entry's own claims did not hold.** The scopes half is exact (`GlobalMemoryScope` reads
  `None`, `SessionMemoryScope` the one session), but the requested width is *not* `k` times the
  pool factor under `CORTEX_MEMORY_RECALL=raw`, whose `candidate_k(k)` is `k` with no over-fetch,
  nor on a fallback line, whose emitted basis is the fallback's while the width was the judge's.
  The correction costs no field, because `available` makes the width redundant rather than merely
  inferable: where it would matter it equals `pool_size`, and where it would not, nothing was cut
  and it explains nothing. **The count's price was measured rather than assumed, and the
  measurement inverted the worry.** An exact `count(*)` is 2.0 ms against a 520 ms ranked search
  over 100k rows, because `memories_scope_idx` serves it as an index-only scan with no heap fetches
  while the search detoasts every row and computes a 768-dimension distance for it; on an
  unvacuumed table it rises to 22 to 31 ms and is still under 6%. So a cap was declined for saving
  nothing worth the weaker answer, and the shape that needs no second read was declined for costing
  **2.85x the plain search**: `count(*) OVER ()` puts a `WindowAgg` under the `Limit` that
  materializes all 100,000 rows, `embedding::text` included, before the top-20 heapsort can discard
  them, and at 20k rows that is invisible, which is how it would have shipped looking free. The
  count is issued only inside the `audit is not None` guard, so an unaudited recall runs no
  counting query at all, and it runs next to the search rather than after the rank, two reads not
  being one transaction with a second of model time available to sit between them. **Distrust
  green:** eight mutations, six in CI and two against real Postgres, each reddening only what it
  should, and the first of them had to be *fixed* rather than watched: the contract check was
  written with three memories, which any count capped at three or more passes, and it caught a
  cutoff-capped count only once it held more memories than the widest pool a shipped deployment
  fetches. **It also closed a gate that was only half a gate**: `memory_contract.ALL_CHECKS` was
  driven solely by the live pgvector run, so a check added to the shared file reached CI only if
  someone wrote it a second time by hand, and a count faked as a length over rows is exactly what
  that would have hidden; the fake now runs the same file in CI. Verified live in the
  `cortex_contract` database (1 passed, 39 deselected), where the `len(rows)` mutation reddens the
  count check on 20 against 25. **Opens nothing:** the two derivable causes are answered by not
  building them rather than filed, and an exact count leaves no bound to revisit.
- **The judge's cost, which is the only reason its default is `raw`, fell twenty-fold on 2026-08-06
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) bounded-side-calls addendum), so the default is
  recommended for a move and the decision is the user's.** The rank's request now carries
  `rank_bounds(k)` (`max_tokens=24 + 8k, thinking=False`), the lever the history fold proved out
  the same day, and a rank whose deliberation `drain_text` throws away unread stopped paying for
  it: 448 to 613 decoded tokens at 18.4 s per recall became 12 to 22 at **0.9 s**, of which about
  0.2 s is evaluating the pool prompt that no bound touches. **The ranking did not change.** Scored
  again over the same ten notes and six questions, the bounded judge returned the identical note
  for every question, mean reciprocal rank 1.000 against the cosine's 0.917, the right note first 6
  of 6 against 5 of 6, no fallbacks, and it still returns *fewer* hits than `k` because it drops
  the notes that do not help. So the premise the default rested on is gone, and two things a
  default still has to answer for are not: a rank runs on **every** turn that recalls, unlike the
  history fold that a cache pays for once per boundary move, so this is 0.9 s on the front of every
  such turn rather than an amortized cost; and the corpus is still hand built by the policy's
  author, ten notes and six questions, which shows the mechanism works and is not a benchmark.
  **Trigger:** the user's call on `CORTEX_MEMORY_RECALL=judge` as a default, or a wider corpus that
  settles the second point on its own. Whichever way it goes, the audit trail
  (`CORTEX_MEMORY_RECALL_AUDIT=1`) reports the basis that actually ranked each recall, so a
  deployment that turns it on can tell a judged rank from a fallback after the fact.
  **The corpus half of that trigger was answered the same day** ([ADR-0038](../adr/ADR-0038-ranked-recall.md)
  widened-corpus section): 41 notes and 26 questions over six categories, five of which the judge
  could have lost, scored through the shipped pool width (the cosine's top 12 of 41, `pool_factor`
  4 at `k` 3, gold in pool for all 22 answerable). The judge is **not worse anywhere**. It ties the
  cosine at MRR 1.000 on the three categories where the geometry is already right (an answer worded
  in the question's own words, two near-duplicate notes, an answer buried in a clause), and beats it
  on two: the vocabulary trap it was bought for (1.000 against 0.806) and, unplanned, superseded
  versions, where the cosine cannot tell a dead fact from its replacement and put the stale one
  first twice in four (1.000 against 0.750). Aggregate 1.000 against 0.902 over the 22 answerable,
  0.75 s per recall, 12 to 20 decoded tokens. A **reversed-cosine control arm scored 0.000 in every
  category**, so the scorer has been watched failing rather than merely trusted. **The default is
  still the user's call and is still not flipped**; what changed is that the recommendation no
  longer rests on a corpus cut to produce it.
  **Called and flipped 2026-08-08, after the measurement the user asked for first**
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) turn-cost addendum). The one thing every earlier run
  had priced was a rank, and this entry's own remaining objection was that a rank is not a turn, so
  the turn was measured before the flag moved. Real turns through the seam on the 24 GB card, one
  fresh pre-seeded session each so no turn's own recorded exchange reached the next one's pool, six
  questions across the six categories, eight repetitions, 48 turns an arm, in **A/B/A order** with a
  raw block either side of the judged one. **Time to first token rises 0.515 s** (95% CI 0.116 to
  0.915, blocked by question and bootstrapped), the whole turn 0.526 s, while the **null arm, raw
  against raw, is -0.158 s with an interval spanning zero**: the harness separates the arms it
  should and not the arms it should not. **The turn pays less than the rank costs.** Timed alone at
  the shape assembly actually asks for (`k` 5 at `pool_factor` 4, a pool of 20 rather than the
  published run's 12) a rank is 0.877 s, above the 0.75 s on record, and the difference is given
  back because the judge hands the reply 1.17 notes where the cosine hands it 5, so the memory block
  the model reads before it can speak is smaller. That saving is proportional to how much the cosine
  over-returns and a deployment whose questions are mostly answerable will see less of it. **The
  rank runs before generation and lands on the first token**, which the trail's own timestamps
  confirm from the other side: everything up to and including the pgvector search is 0.363 s judged
  against 0.396 s raw, the same number, and the whole difference sits after it. **It is paid every
  turn.** `JudgeRecallPolicy` holds no cache, `MemoryRecaller.recall` calls `select` on every
  recall, and the run logged exactly 48 recall lines for 48 turns per arm, so the asymmetry with the
  fold that this entry kept naming is confirmed rather than softened; only its size changed. The
  ranking was re-read at the wider pool off the same trail and did not suffer for it: **MRR 1.000
  against the cosine's 0.767 over 40 answerable turns, nothing returned on all 8 unanswerable ones
  against 0 of 8, and 0 fallbacks in 48 recalls.** `CORTEX_MEMORY_RECALL=raw` is the opt-out now.
  What no run of this repo's own can settle is unchanged: the corpus is hand built by an interested
  party, and what the flip changes is that a real conversation is now what the rank meets.
- **A considered abstention is indistinguishable from a failed rank, found by the wider corpus on
  2026-08-06 ([ADR-0038](../adr/ADR-0038-ranked-recall.md) widened-corpus section).** Four of the
  26 questions have no answer anywhere in the corpus, and the model got all four right: asked which
  notes help, it replied `{"order": []}`, valid and complete rather than truncated, which was
  confirmed by re-sampling each fallback and reading the raw text rather than inferring it from the
  basis. `JudgeRecallPolicy.select` treats an empty parse as a failure, so all four fell back and
  the caller got the cosine's top three irrelevant notes instead. The one thing the judge can do
  that no geometric policy can, decline to answer, is the one thing the policy cannot express, and
  at the port it looks exactly like an unreachable model. **Cost:** not behind the unchanged seam
  in the cheap sense. A third `RankBasis` (an abstention distinct from `VERDICT` and from the
  fallback bases) plus a `select` that returns an empty `Ranking` changes what a recall may hand a
  turn, so the recaller, the audit trail and the prompt assembly each need to mean something by
  zero hits. **Trigger:** flipping the default to `judge`, since the defect is invisible while the
  policy is off, or the first report of memory answering a question it has nothing about.
  **Landed 2026-08-07 ahead of its trigger** ([ADR-0038](../adr/ADR-0038-ranked-recall.md)
  abstention addendum), because the fix is small and the entry's own reason for deferring it was the
  blast radius, which the code did not confirm. `RankBasis` gained `DEMUR`, the judicial sibling of
  `VERDICT` for a reader who decided that nothing in the pool makes the case (a demurrer grants
  every word of the material and still finds no case; `NONSUIT` was more exact and less readable,
  `SILENCE` would have fitted an empty store as well as a refusal, and `ABSTAIN` says no decision
  was made, which is the opposite of what happened). `parse_order` now has three outcomes rather
  than two: `None` for a reply nothing can be read out of, **including one that named notes of which
  none exists**, since a model that tried to pick and produced nothing pickable has failed rather
  than declined; `()` for an `order` that arrived empty; and the picks otherwise. `select` returns
  `Ranking(hits=(), basis=DEMUR)` for the middle case and never consults the fallback, which stays
  exactly where it was for real failures. **Cost correction:** this entry priced three consumers
  needing to mean something by zero hits, and two of the three already did. `MemoryRecaller.recall`
  returns `ranking.memories`, so an empty ranking was already an empty sequence and nothing
  re-fetched or substituted the pool; `_recalled_context` (`turn_context.py`) already returned
  `None` on no hits, so the turn was already assembled without a memory block. Only the trail needed
  the new basis, and it needed no new field for it, since `demur` with no hits, another basis with
  no hits, and a fallback's basis with hits are three readings of fields the line already carried.
  What the entry did not price and the close added is an invariant: a `DEMUR` ranking carrying hits
  is refused at construction, because a policy cannot both decline and return something. CI-gated at
  100% over the fakes, with the empty-pick path proved able to fail by restoring the old
  `if not order` branch (three tests redden, including the turn-assembly one). **Measured live on
  the same 41-note corpus that found it**: the four unanswerable questions now return nothing, 4 of
  4, the whole run fell back 0 of 26 where it fell back 4 of 26, and the ranking on the 22
  answerable questions is unchanged (aggregate MRR 1.000 against the cosine's 0.902, the
  reversed-cosine control still 0.000) at 0.76 s per recall. Declining costs what ranking costs,
  because the pool prompt is evaluated either way.
- **A geometric policy still cannot decline, opened 2026-08-07 by the abstention close
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) abstention addendum).** The refusal that landed is
  the judge's alone. `RawRecallPolicy` (the default) and the three heuristic policies always return
  their nearest `k`, so on a question memory cannot answer, every deployment that has not opted into
  `CORTEX_MEMORY_RECALL=judge` still receives three nearest misses, which is the same turn the
  closed entry described and a different cause. **The premise inverted on 2026-08-08 without the
  entry closing**, when the default moved to `judge` (the turn-cost addendum): the shipped stack can
  decline now, and what cannot is a deployment that sets `CORTEX_MEMORY_RECALL` to `raw` or to one
  of the heuristics, which is an opt-out rather than the path of least resistance. That makes the
  entry smaller and not moot, since the reasons the floor was declined are about the floor and not
  about how many deployments meet the gap. The geometric analogue is a **relevance floor**: a
  policy that drops a candidate below some similarity and may therefore return nothing, which the
  `Ranking` the port now returns can express and no policy computes. It was considered during the
  close and declined on two counts that would have to be answered first. A cosine threshold is not
  portable across embedding models, since the absolute values a floor is calibrated against belong
  to whichever `Embedder` produced them and mean something else behind another one. And a floor on
  `RawRecallPolicy` changes the founding behavior, the one policy whose promise is that recall is
  byte-for-byte v1, so the floor belongs on a fifth policy rather than on the default. **Trigger:**
  a deployment that wants recall to stay geometric and still be able to say nothing, which is also
  the shape the first complaint about irrelevant recalled memories under the shipped default would
  take, or a calibration run that gives the floor a defensible number.
  **Closed 2026-08-08 as declined on measurement, the second arm of its own trigger having been run**
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) relevance-floor addendum). **The consumer was bigger
  than the entry's own framing**, which is the first thing the re-derivation turned up and the reason
  this was measured rather than shrugged at: `recall_policy_from_config` (`memory_builders.py`)
  builds `JudgeRecallPolicy` with no `fallback` argument, so the shipped default carries
  `RAW_RECALL_POLICY` and hands it the pool on an `InferenceError`, on a reply outside the envelope,
  and on an order that parses to nothing usable. The cosine therefore ranks inside the **default**
  deployment every time the model cannot be reached or believed, which is exactly the moment nothing
  else is watching, so a floor would have been a default-path guard and not the opt-out nicety this
  entry describes. **The design was settled before the measurement could bias it, and it is not the
  fifth policy this entry proposes:** a fifth `MemoryRecallName` is a policy a deployment runs
  *instead of* the judge, which leaves that fallback exactly as unfloored as it is today, and it
  multiplies the matrix because a floor is orthogonal to how you rank. The shape that composes is a
  decorator over an inner `RecallPolicy` (the shape the judge's own fallback already is) plus one
  knob defaulting to `0.0`, which protects the founding byte-for-byte promise by the default rather
  than by a separate name, thresholds `hit.score` because `SPREAD` and `SWEEP` keys are measured
  against the kept set and do not compare, pre-filters the pool so no new `RankBasis` is needed, and
  never wraps the judge itself, since the vocabulary trap is precisely where the answering note's
  cosine is low. **None of it survives the calibration.** Measured on the real embedder over this
  area's own 41-note corpus at the shipped pool width, with a third population added for the
  purpose (8 questions about subjects no note mentions), the answerable and unanswerable bands
  overlap: gold notes score 0.4742 to 0.9063 while the four adjacent unanswerable questions top out
  at 0.5112 to 0.6325, a separation of **0.1582 negative**, and even the wholly unrelated questions
  reach 0.4994 against a lowest answerable gold of 0.4742. The tightest floor that silences all four
  unanswerable questions, 0.6325 and derived from the data rather than picked off a grid, costs
  **6 of 22 answerable ones outright**, takes MRR from 0.902 to 0.659, and drops the `TRAP` category
  from 0.81 to **0.17**, which is the vocabulary trap the model rank exists for. That is the cheapest
  the promise ever gets. Behind the alternative embedder the conclusion holds (separation 0.1933
  negative, the tightest floor 0.4485 at 7 of 22 and `TRAP` 0.00) while
  every number moves, so the entry's portability objection is now measured rather than asserted. The
  safe range and the useful range do not even overlap behind the shipped embedder: a floor costs
  nothing only at or below the lowest answerable gold, 0.4742, while catching even the easiest
  population needs 0.4995, so they cross by 0.0253. Behind the alternative embedder they do overlap,
  by 0.0068, which is a knob whose whole safe and useful range is seven thousandths wide, read off
  the sample minimum of 22 hand-built questions rather than off a bound, and narrowing on a real
  store where more notes mean a closer nearest neighbour for every question. **What the run establishes instead is why the shipped default is what
  it is:** an abstention is a property of reading and not of ranking, since a question memory cannot
  answer has the same geometry as a question whose answer is worded unlike it, so
  `CORTEX_MEMORY_RECALL=raw` is an opt-out of exactly that capability and the runbook now says so.
  The calibration ships as `packages/inference/tests/test_recall_floor_live.py` rather than staying
  in a scratchpad, needing only the CPU embedder, and its instrument was proved able to fail before
  its result was believed: an operator that drops a hit reddens the floor-of-zero identity, one that
  ignores its floor reddens the absurd end, and the finding assertion itself fails with **+0.2104**
  on a corpus restricted to the categories whose populations do separate, which is the reopening
  condition wired as a test. **Reopens** behind an embedder whose populations separate, or on a
  signal that is not an absolute cosine; the already-filed **cross-encoder** rank is the candidate,
  since it reads the pair rather than measuring the distance. Nothing opened in its place.

- **A dead embedder or a dead memory store kills the turn rather than costing it its memory,
  opened 2026-08-11 by the `Embedder` contract list
  ([ADR-0008](../adr/ADR-0008-memory-v1.md)).** *Fix when it bites.* The port documents one
  failure channel, `EmbedderError`, and the pgvector adapter documents `MemoryStoreError` beside
  it, and writing the shared checks turned up the fact that **nothing in the brain catches
  either**. `recall_memory_context` (`turn_context.py`) awaits `caps.memory.recall(...)` bare,
  `MemoryRecaller.recall` awaits `embed` bare, and the engine's only handler is for
  `InferenceError`, so an embedding server that is down or a Postgres that is unreachable does not
  cost a turn its recalled notes, it fails the turn. That is the opposite bias from every other
  optional capability here: a dead tool sidecar is served around and reported
  (`SkipUnavailableToolRegistry`), a body that will not answer becomes a recoverable tool result,
  a subagent that cannot be admitted degrades to an `ok=False` result. Memory is the one that
  takes the whole turn down with it, and it is the capability a turn most obviously has an answer
  without.
  **What it is not is a hole in the checks.** The shared list holds both implementations to
  raising `EmbedderError` rather than their own backend's exception, which is what makes a single
  catch possible at all; what is missing is the catch. The fix is a decision rather than a line:
  where it belongs (`recall_memory_context`, which already answers `None` for memory being
  switched off, so a failure reading as "no memories this turn" needs no new shape), whether the
  user is told (a turn that silently forgets is its own kind of wrong, and the degraded-mode
  precedent reports rather than hides), and whether a write failing is the same call as a read
  failing (`remember` losing an exchange is a durability question, not a context one).
  **Trigger:** the first live turn taken against a stopped embedding server or a stopped Postgres,
  which the memory runbook's own teardown step makes easy to hit by accident, or the degraded-mode
  question being answered for any other optional capability.
  **Closed 2026-08-11**, hours after it opened and **ahead of its trigger, neither arm of which
  fired**: no live turn had been taken against a stopped server, and no other optional capability
  had had its degraded-mode question reopened. It was taken because the entry's only blocker was
  the decision it named, and the decision was available. The defect was re-derived by running
  rather than by reading, as this file's own standing warning demands: a `TurnEngine` over the
  in-memory session store with a `HashEmbedder` told to `fail_with` answered `TURN FAILED with
  EmbedderError` where the same turn with a live embedder answered in four events, so the entry's
  account was still exact. Two of its own guesses were tested against the tree and both held, the
  method name being `_recalled_context` rather than `recall_memory_context`. What landed is in the
  [ADR-0008](../adr/ADR-0008-memory-v1.md) unavailable-memory addendum: `EmbedderError` and
  `MemoryStoreError` degrade on both halves and nothing else does, the read in `_recalled_context`
  and the write in `record_exchange`, which are also the two functions `BrainPhase` shares with
  `TurnEngine`, so the deep model's phase degrades identically with no second copy. The entry's
  hardest question, whether a failed write is the same call as a failed read, resolved to **both
  degrade for opposite reasons**: the read because the turn genuinely has an answer without its
  notes, the write because **raising cannot save it**, the reply having streamed and the assistant
  message being persisted before `record_exchange` runs, so an exception there loses the memory
  just the same and takes a turn the user has read with it. The exchange is not the thing lost
  either, staying in the conversation the user can scroll to; what is lost is a derived index
  entry, which is why the write logs an `error` and the read a `warning`. On being told, the entry
  guessed right that the precedent reports rather than hides, and the report is unconditional on
  the module logger rather than a line on the opt-in recall trail, an outage visible only where
  `CORTEX_MEMORY_RECALL_AUDIT` is on being the silence rather than the cure. The trail gains an
  omission instead: no line is written for a recall that never happened, so `pool == available`
  goes on meaning the pool was the whole readable store rather than acquiring a `0 == 0` reading
  for a store nobody could reach. The user is told once, about the read only, by one app-authored
  `StatusUpdate(state="forgoing")` on the channel a fold already narrates itself on, which earns
  its chip where the silently-lost recap does not because a recap compresses history the user can
  still scroll to while a recalled memory is knowledge from other conversations they cannot see
  and cannot supply. **Two opened in its place**, both residue of this close rather than found
  beside it, and they are the next two entries here.

- **`MemoryStoreError` covers an unreachable backend and a malformed row alike, so a data defect
  now degrades wearing an outage's clothes, opened 2026-08-11 by the unavailable-memory close
  ([ADR-0008](../adr/ADR-0008-memory-v1.md)).** *Fix when it bites.* The line the close drew is
  that a port's declared failure may degrade and anything else is a defect that must propagate,
  and it delegated the drawing of it to the adapters, on the argument that they wrap a backend
  that could not be reached and wrap nothing else. That argument is true of `_WRAPPED` and false
  of the second `except` in `PgVectorMemoryStore.search` and `count_candidates`, which wrap
  `(KeyError, IndexError, TypeError, ValueError)` from a malformed row or an unreadable total into
  the same `MemoryStoreError`. A corrupt row therefore reaches a turn as an outage and costs it
  its notes quietly rather than failing loudly, which is exactly the swallowing the close said it
  would not do. It is visible (the `warning` carries the traceback and the adapter's own
  "malformed memory row in search result"), so this is a sharpening rather than a hole. The shape
  is the `ModelNotHostedError` precedent: a subclass of `MemoryStoreError` for the data failures,
  so every existing `except MemoryStoreError` keeps catching it, plus a narrower `except` ahead of
  the degrading one in the two core catches. **Trigger:** the first malformed row anybody actually
  meets, or the next port to draw this same line, since the rule wants to be one rule.

- **The `MemoryStore` shared check list has no backend-failure check where the `Embedder` list has
  one, opened 2026-08-11 by the unavailable-memory close
  ([ADR-0008](../adr/ADR-0008-memory-v1.md)).** *Fix when it bites.* The close needed a store that
  could be taken away and found that only the embedder had one, so `InMemoryMemoryStore.fail_with`
  landed as a twin of `HashEmbedder`'s rather than as a check both implementations answer. What
  that leaves is the asymmetry the `Embedder` list exists to remove: "every failure crosses the
  port as `MemoryStoreError`" is held by `test_pgvector.py` on one side and by one core test on
  the other, twice rather than once, which is the arrangement `memory_contract.ALL_CHECKS` was
  driven over both implementations to end. It is not free, because the checks take a bare
  `MemoryStore` and the knob makes them take a pair, so all ten signatures move and the live
  pgvector arm needs a way to break its own backend (closing the pool is the obvious one). **Fix
  when it bites**, and the bite is a second implementation of the port, or an adapter found
  letting a backend exception through, which is the thing a shared check would have caught.
