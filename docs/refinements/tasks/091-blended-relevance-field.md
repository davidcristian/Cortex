# A distinct blended-relevance field

**Status:** landed 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The three rerank entries
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

## Trail

- 2026-07-16: Closed as declined for want of a consumer, the first entry in this area to close as
  declined. It was read against the tree rather than argued: nothing reads `ScoredMemory.score` at
  all, which its own origin addendum had made the condition, so cheapness had been standing in for
  readiness. It moved to the index's dead-until-a-consumer list, and the pass that closed it opened
  recall observability behind it, which is both why the question was hard to answer and the consumer
  that would reopen it. The close is recorded at the [ADR-0008 relevance-field
  addendum](../../adr/ADR-0008-memory-v1.md).
- 2026-08-06: The decline was reversed when `RecallPolicy.select` was widened once for all three of
  its waiting consumers. The reversal is about placement rather than verdict: the key a policy
  ranked by is `RankedMemory.key` on the policy's own return and never a second field on
  `ScoredMemory`, so the store's score goes on meaning the raw cosine exactly as the close insisted.
