# A distinct blended-relevance field

**Status:** done 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

Reporting the blended relevance a rerank policy ordered by, as a value of its own beside the
store's raw cosine. The three rerank entries ([R-088](088-recency-rerank-dedup.md),
[R-089](089-mmr-diversity-policy.md), [R-090](090-recency-and-diversity-recall.md)) each listed
it as the one deferral that needed no port change.

Two findings closed it as declined in 2026-07-16. **Nothing reads a recall score.**
`ScoredMemory.score` is written by both store adapters and read only by the policies themselves,
as an input, and by tests. The one production consumer of a recall result,
`TurnEngine._render_memory_context` in `engine.py`, reads `record.text`, `record.tainted` and
`record.id`, never `score`. No memory message exists in `proto/body.proto`, and the recall path
had no logging and no audit sink. **And there is no single blend to report.**
`RerankingRecallPolicy` ranks by the recency blend, which is comparable across hits, while
`MmrRecallPolicy` and `RecencyMmrRecallPolicy` rank by an MMR objective computed against the kept
set at pick time, which depends on order and so is not comparable between hits in one result.

Tested live against pgvector: the adapter reports cosine similarity (a probe row at distance
0.0002 came back as score 0.9998), and under `reranked` the emitted order was scores 0.6000,
0.9998, 0.7071, which the reported field does not explain while the blend (0.7131, 0.6999,
0.5700) does.

## History

- 2026-07-16: Closed as declined for want of a consumer, the first entry in this area to close
  that way, and recorded at [ADR-0008](../../adr/ADR-0008-memory-v1.md). The pass that closed it
  opened recall observability ([R-094](094-recall-observability.md)) behind it, which is both why
  the question was hard to answer and the consumer that would reopen it.
- 2026-08-06: The decline was reversed when `RecallPolicy.select` was widened once for all three
  of its waiting consumers. The change is about placement rather than about the earlier
  conclusion: the key a policy ranked by is `RankedMemory.key` on the policy's own return, and
  never a second field on `ScoredMemory`, so the store's score still means the raw cosine.
