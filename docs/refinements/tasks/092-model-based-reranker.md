# The model-based reranker

**Status:** done 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

A recall policy that asks a model which candidates to keep, rather than ranking them by cosine.
The three rerank entries ([R-088](088-recency-rerank-dedup.md),
[R-089](089-mmr-diversity-policy.md), [R-090](090-recency-and-diversity-recall.md)) each deferred
it behind the synchronous `RecallPolicy.select` and a GPU-lease problem.

It shipped 2026-08-06 as `JudgeRecallPolicy`, when `select` was widened once for all three of its
deferred consumers. It was measured against the shipping cosine at 0.917 to 1.000 mean reciprocal
rank on a small corpus built to make the two disagree.

## History

- 2026-07-16: Audited against the code and kept deferred with its blocker made precise. The async
  widening of `select` is contained: it has one production caller, `MemoryRecaller.recall` in
  `recall.py`, which is already async, and none of the four implementers calls another's `select`.
  The GPU-lease problem was overstated. Recall runs inside `_inference_messages`, which
  `handle_turn` awaits to completion before the reply stream takes the resident model's
  non-reentrant lock, so at reranking time the turn does not hold the lease. A reranker that
  fully drains its model call is a sequential acquire, which is the title generator's approach
  and was tested against the real manager: a drained acquire followed by the reply's acquire
  succeeds, while a call held open across it deadlocks. The real risk is an abandoned reranker
  stream, not nesting. The audit then added a hardware blocker, that a model pass could not be
  checked on the 8 GB dev GPU. Recorded at [ADR-0008](../../adr/ADR-0008-memory-v1.md).
- 2026-07-19: That hardware claim was struck as false.
  [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured the real cortex plus its
  vision projector resident on that card at `-ngl 99 --ctx-size 4096 --parallel 1`, and
  [ADR-0030](../../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of the
  card's 8188 MiB, so only a 16K production context was out of reach. What remained was
  sequencing: the blended-relevance field and recall observability both resolve to a `select`
  widening, and the guidance was to change `select` once for all three rather than twice.
- 2026-08-06: Shipped as `JudgeRecallPolicy`. Two claims of the audited entries did not hold: the
  caller they name, `_inference_messages` in `engine.py`, no longer exists, and neither entry
  recorded that `select` did not receive the query, so the widening was three changes rather than
  two.
- 2026-08-06: The GPU-lease problem was settled as sequencing rather than a new lock: a
  `drain_text` helper that leaves the adapter's acquire block in a `finally`, which the title
  generator now uses as well.
- 2026-08-06: The index kept a list of work that stays in this backlog although it needs the
  host's hardware to observe or judge. This entry's model pass left that list by being run and
  measured against the real cortex in Docker, the same day the model passes behind history
  summarization left it by being built.
