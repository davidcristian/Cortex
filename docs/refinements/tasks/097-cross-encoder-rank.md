# A cross-encoder rank

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a judge quality reading taken over memories nobody wrote for the measurement (neither the ten notes inline in `test_rerank_judge_live.py` nor the 41 in `recall_corpus.py`), in which the judge drops an answerable note the cosine kept or ranks worse than it; or a first-token or whole-turn latency budget written into an ADR decision or a config bound that the recorded rank cost of 0.877 s, or its +0.515 s on the first token, exceeds. Neither exists in the tree today. The first needs a deployed store's memories, which live in its Postgres volume, so it can enter the tree only as a recorded result. Both depend on `CORTEX_MEMORY_BACKEND` naming a store and `CORTEX_MEMORY_RECALL=judge`, and the cost on `CORTEX_MEMORY_RECALL_POOL_FACTOR` and `DEFAULT_RECALL_K`.
**Verified:** 2026-09-17

Recorded inside the ranked-recall entry ([096](096-ranked-recall-widening.md)), as one of the two deferrals that close opened when the
model rank, the blended key and the recall trail landed together:

> Still open here: a **cross-encoder** rank, which is the other form of a model reranker
> and wants a scoring-model port rather than a chat completion, so it is a new adapter and not a
> policy (trigger: a measured shortfall of the judge on a real corpus, or a latency budget it
> cannot meet);

The relevance-floor decline named it again as the candidate signal:

> **Reopens** behind an embedder whose populations separate, or on a
> signal that is not an absolute cosine; the already-filed **cross-encoder** rank is the candidate,
> since it reads the pair rather than measuring the distance.

## Trail

- 2026-08-06: Opened by the ranked-recall close as the other form of a model reranker, wanting a
  scoring-model port rather than a chat completion and so a new adapter rather than a policy. It was
  one of the two that close opened and that neither the index cell nor the area header picked up
  until the arithmetic correction later the same day took the area's count from 7 to 9.
- 2026-08-08: Named as the candidate when the geometric relevance floor closed as declined on
  measurement, since a cross-encoder reads the pair rather than measuring an absolute cosine, which
  is the signal the calibration showed cannot separate the answerable from the unanswerable.
- 2026-09-11: read against the tree and not fired. No cross-encoder or scoring-model port exists:
  `grep -rni 'cross.encoder\|scoring.model' brain/packages/*/src` finds nothing, and the reranker
  surface in `cortex_core` is still the chat-completion judge (`rerank_judge.py`, `JudgeRecallPolicy`)
  over `rerank.py`, `rerank_math.py` and `rerank_policies.py`. Neither half of the trigger has fired.
  The only quality reading on record is the bounded-side-calls addendum's, where the judge ties the
  cosine wherever the cosine is right and beats it wherever the cosine is wrong, which is the
  opposite of a shortfall, and it was taken on the widened four-category corpus rather than on a
  deployed store's own memories. No latency budget for the judge exists anywhere in the tree to be
  missed: the harness addendum measures the judge's extra cost per turn and attributes it partly to
  the rank and partly to an honest refusal's length, without setting a bound. The origin ADR still
  lists this rank as deferred on the same trigger and the relevance-floor decline still names it as
  the candidate signal.
- 2026-09-17: not fired, and neither half is decidable from the tree as it was written. The grep for
  a cross-encoder or a scoring-model port over `brain/packages/*/src` still finds nothing, and no
  commit since the last reading touched the `rerank` modules, the two corpora or their live tests,
  while none of the five addenda ADR-0038 gained in that time mentions the judge. The tree
  does hold judge measurements, and none of them can decide the trigger. On latency, the turn-cost
  addendum times a rank at 0.877 s (pool of 20 at `DEFAULT_RECALL_K` 5 and `recall_pool_factor` 4)
  and the turn's first token at +0.515 s against the cosine, but no ADR decision or setting states a
  budget either number could miss. On quality, every reading is over notes written for the
  measurement: the ten inline in `brain/packages/inference/tests/test_rerank_judge_live.py`, and the
  41 in `recall_corpus.py` beside it, read by `test_rerank_judge_wide_live.py` and the turn-cost
  probe, whose own docstring says no sampling of real memories was involved. A real corpus is a
  deployed store's Postgres volume, which no commit carries. The trigger now names both halves in a form a reader can check, and the
  settings they depend on: with the memory backend at its default `none`, or `CORTEX_MEMORY_RECALL`
  set to anything but its default `judge`, the judge never runs and neither half can arrive.
