# Model rank, blended key, and recall trail

**Status:** landed 2026-08-06
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`RecallPolicy.select` was widened once, for all three:
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
request and falls back to another policy on any failure to reach it or to accept its answer, the emitted basis
then being the fallback's so the trail says what actually ranked. **Measured against the cosine
that ships**, on ten notes and six questions worded so the answer shares no vocabulary with the
question while a distractor shares plenty: mean reciprocal rank 0.917 to 1.000, the correct note
placed first 5 of 6 times against 6 of 6, no fallbacks, and the judge returned *fewer* than `k`
because it drops notes that do not help, which is a larger win in the turn's context than in the
ranking. It costs a full cortex generation per recall, so the default stays `raw`. **Two claims of
the audited entries did not hold.** Both name `_inference_messages` in `engine.py` as the caller,
a method that no longer exists (it is `MemoryRecaller.recall` in `recall.py` for this port, still
`async`, so the substance held); and neither recorded that **`select` did not carry the query**, so
the widening was three changes rather than two, which is the one place their cost estimate was
too small. Still open here: a **cross-encoder** rank, which is the other form of a model reranker
and wants a scoring-model port rather than a chat completion, so it is a new adapter and not a
policy (trigger: a measured shortfall of the judge on a real corpus, or a latency budget it
cannot meet); and **auditing the candidates that were dropped**, which `RecallAudit` does not
carry because a non-picked candidate's `SPREAD`/`SWEEP` key is not well defined (trigger: the
first investigation that needs to know why a specific memory was *not* returned).
**The dropped candidates landed 2026-08-09, ahead of that trigger and because the default moved
under it** ([ADR-0038](../../adr/ADR-0038-ranked-recall.md) dropped-candidate addendum). The entry
was filed as fix-when-it-bites against a trail nobody was reading yet; what changed is that
`CORTEX_MEMORY_RECALL` ships as `judge`, which is measured returning 1.17 notes where the cosine
returned 5, so the recall trail was thinnest exactly where most of the pool now disappears.
**The stated obstacle is real, and it settles what the line can carry.** There is no `SPREAD`/`SWEEP` key for a
candidate that never joined a kept set, and there is no `VERDICT` key either, since the judge
leaves an unhelpful note out of its order rather than scoring it low; under `ECHO` and `EMBER` a
key could be computed after the fact, which is not the same as having one, a `Ranking` carrying
keys for the hits it kept and for nothing else. What exists for every candidate under every basis
is the store's own cosine, the store having produced the pool, so the close logs the id and that
cosine and omits the key that does not apply. The line now carries
`dropped`, one id and score per candidate the rank passed over, and `dropped_omitted`, so an id
in neither `hits` nor `dropped` was never a candidate at all, which is the distinction an
investigation actually arrives with and the one a pool *count* could never draw. **What it
deliberately cannot say is why**: a rank records a judgment only about what it kept, so the
trail is an account of what was available. **Bounded at 20**, the whole pool a default deployment
fetches (`DEFAULT_RECALL_K` 5 at `pool_factor` 4), so a shipped line never truncates and the
bound bites only on a wider over-fetch, where a line growing with the pool would make the trail
the thing worth turning off; what it cuts is the tail of the store's own order and the count of
what it cut rides the line. Text is absent structurally rather than by the sink omitting it,
`DroppedCandidate` having no field that could hold any. Hexagonal placement is the core's
`dropped_candidates(pool, ranking)` for the difference and the bound, the sink for the emission
and nothing else. **Cost correction:** the entry priced nothing, and the shape it implied (a key
per dropped candidate) does not exist; what shipped is two value types, one pure function, one
required `RecallAudit` field and two log keys, all inside the existing `RecallAuditSink` port.
The audit stays opt in and off still costs nothing, the whole record being assembled inside
`MemoryRecaller.recall`'s `audit is not None` guard, which an instrumented pool counting its own
walks pins at 1 unaudited against 2 audited rather than leaving to inspection. **Opens one**, the
entry below: the line can now say a memory was never a candidate, and still cannot say why.

## Trail

- 2026-08-06: The model-based reranker, the declined blended-relevance field and recall
  observability landed together, which is what the reranker audit said they would have to do.
  `RecallPolicy.select` was widened once, to `async def select(hits, *, query, now, k) -> Ranking`.
- 2026-08-06: The close did half of its own bookkeeping, striking the model-based reranker and
  recall observability from the area header when they landed and never adding the two deferrals it
  opened, so the area's count was corrected from 7 to 9 the same day. That pass repaired three more
  navigation lines without any count being wrong with them.
- 2026-08-06: Both deferrals this close opened were written up in the entry itself and at the origin
  decision within the hour of the close, so what that correction repaired was the navigation and not
  the record.
- 2026-08-09: The audit of the candidates a rank dropped landed, ahead of its trigger and because
  the default had moved to `judge` underneath it, a judge keeping about one note where the cosine
  kept five having left the recall trail thinnest exactly where most of the pool now disappears.
