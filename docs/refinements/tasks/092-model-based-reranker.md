# The model-based reranker

**Status:** landed 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The rerank, MMR, and
recency-and-diversity entries above each keep it deferred behind the sync `RecallPolicy.select`
and the shared GPU-lease hazard. Audited against the code, the first cost is bounded and the second
is misframed, but it stays deferred, alongside the summarization half it shares a design with (see
[session-history.md](../index.md#session-history)). **The async widening is clean and contained.**
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
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured the real cortex plus its vision
projector resident on that card at `-ngl 99 --ctx-size 4096 --parallel 1`, and
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
8188 MiB, so a rank over a handful of candidates is judgeable agent-side today and only a 16K production context
is out of reach. What binds is sequencing, and it always was: the declined blended-relevance field
and the recall-observability entry both resolve to a `RecallPolicy.select` widening, and the
recorded guidance is to change `select` once for all three consumers (a model rank, the distinct
blended field, an observability sink reading the rank key) rather than twice; an async-only
widening now would be the first of two changes. So this reopens when that widening is taken,
landing the async change, the richer `select` return, and the model policy as one design.

## Trail

- 2026-07-16: Audited against the code and kept deferred with its blocker sharpened. The async
  `select` widening is mechanically clean and contained, one already-async production caller with no
  colour cascade upward, and the non-reentrant GPU-lease hazard is navigable by the title
  generator's sequential-drain discipline rather than being the structural nesting this entry's
  framing implied. The audit then named a hardware blocker, that a model pass cannot be
  behaviour-validated on the 8 GB dev GPU where the cortex tier does not fit. It is recorded at the
  [ADR-0008 reranker-audit addendum](../../adr/ADR-0008-memory-v1.md).
- 2026-07-19: That hardware clause was struck as false, the card having been measured holding the
  real cortex beside its vision projector, so only a 16K production context is out of reach.
- 2026-08-06: Landed as `JudgeRecallPolicy` when `select` was widened once for all three of its
  deferred consumers, measured against the shipping cosine at 0.917 to 1.000 mean reciprocal rank on
  a small built-for-disagreement corpus. Two claims of the audited entries did not hold: the caller
  they name, `_inference_messages` in `engine.py`, no longer exists, and neither noticed that
  `select` did not carry the query, so the widening was three changes rather than two.
- 2026-08-06: The GPU-lease hazard this entry was deferred behind was settled as sequencing rather
  than as a new lock: a `drain_text` helper that leaves the adapter's acquire block in a `finally`,
  the same helper the title generator now uses.
- 2026-08-06: The index kept a list of work that stays in this backlog despite needing the host's
  hardware to observe or judge, because the work itself is code and belongs with its area, and this
  entry's model pass left that list by being run and measured against the real cortex in Docker, the
  same day the model passes behind history summarization left it by being built.
