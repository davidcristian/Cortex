# Model rank, blended key, and recall trail

**Status:** done 2026-08-06
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`RecallPolicy.select` was widened once for all three waiting consumers. It is now
`async def select(hits, *, query, now, k) -> Ranking`.

- **The blended key.** The key a policy ranked by is `RankedMemory.key` on the policy's own
  return, never a second field on `ScoredMemory`, so the store's score still means the raw cosine.
  `RankBasis` (`ECHO`, `EMBER`, `SPREAD`, `SWEEP`, `VERDICT`) names which key was used, and its
  `comparable` property records that an MMR key is measured against the kept set and so cannot be
  compared with another hit's.
- **Recall observability.** The `RecallAuditSink` port plus `LoggingRecallSink` in
  `cortex_memory/audit.py` writes one structured line per recall with the pool size, the basis,
  and each kept hit's id, score, key and taint flag, and no text at all.
  `CORTEX_MEMORY_RECALL_AUDIT=1` turns it on.
- **The model rank.** `JudgeRecallPolicy` in `rerank_judge.py`
  (`CORTEX_MEMORY_RECALL=judge`) sends the over-fetched pool to the resident cortex as a numbered
  list under a JSON-schema-constrained request, and falls back to another policy when it cannot
  reach the model or accept its answer. The emitted basis is then the fallback's, so the trail
  says what actually ranked. Measured against the shipping cosine on ten notes and six questions
  worded so the answer shares no vocabulary with the question while a distractor shares plenty:
  mean reciprocal rank 0.917 to 1.000, the correct note placed first 5 of 6 times against 6 of 6,
  no fallbacks, and the judge returned fewer than `k` because it drops notes that do not help. It
  costs a full cortex generation per recall, so the default stayed `raw`.

Two claims of the audited entries did not hold. Both named `_inference_messages` in `engine.py`
as the caller, a method that no longer exists (it is `MemoryRecaller.recall` in `recall.py`, still
async, so the substance held), and neither recorded that `select` did not receive the query, so
the widening was three changes rather than two.

**The dropped candidates shipped 2026-08-09**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 13), ahead of their trigger, because
`CORTEX_MEMORY_RECALL` had moved to `judge`, which returns 1.17 notes where the cosine returned
5, leaving the trail thinnest exactly where most of the pool disappears. A dropped candidate has
no `SPREAD` or `SWEEP` key, since it never joined a kept set, and no `VERDICT` key either, since
the judge leaves an unhelpful note out of its order rather than scoring it low. What every
candidate does have under every basis is the store's own cosine, so the line records the id and
that cosine and omits the key. It records `dropped`, one id and score per candidate the rank
passed over, and `dropped_omitted`, so an id in neither `hits` nor `dropped` was never a
candidate at all. The line cannot say why a candidate was passed over: a rank records a judgment
only about what it kept.

Still open from this close: a cross-encoder rank ([R-097](097-cross-encoder-rank.md)), which
reads the pair rather than completing a chat and so needs a scoring-model port. The
dropped-candidate work opened [R-098](098-never-a-candidate.md), which asks why an id is in
neither list.

`dropped` is bounded at 20, the whole pool a default deployment fetches (`DEFAULT_RECALL_K` 5 at
`pool_factor` 4), so a shipped line never truncates; what the bound cuts is the tail of the
store's own order, and the count of what it cut is on the line. Text cannot appear, because
`DroppedCandidate` has no field that could hold any. The core computes
`dropped_candidates(pool, ranking)` and the sink only emits. The audit stays opt-in and costs
nothing when off: the whole record is assembled inside `MemoryRecaller.recall`'s
`audit is not None` guard, and an instrumented pool counting its own walks measures 1 unaudited
against 2 audited.

## History

- 2026-08-06: The model-based reranker, the declined blended-relevance field and recall
  observability shipped together, which is what the reranker audit said they would have to do.
- 2026-08-06: The close struck the model-based reranker and recall observability from the area
  header but never added the two deferrals it opened, so the area's count was corrected from 7 to
  9 the same day, along with three more navigation lines.
- 2026-08-06: Both deferrals were written up in this entry and at the origin decision within the
  hour, so that correction repaired navigation rather than the record.
- 2026-08-09: The audit of the candidates a rank dropped shipped, ahead of its trigger, because
  the default had moved to `judge`.
