# A cross-encoder rank

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a judge quality reading taken over memories nobody wrote for the measurement (neither the ten notes inline in `test_rerank_judge_live.py` nor the 41 in `recall_corpus.py`), in which the judge drops an answerable note the cosine kept or ranks worse than it; or a first-token or whole-turn latency budget written into an ADR decision or a config bound that the recorded rank cost of 0.877 s, or its +0.515 s on the first token, exceeds. Both figures are the cortex judge's; the deep phase's judge asks the deep model, whose rank alone costs 0.89 s at `k` 3 over a pool of 12. Neither exists in the tree today. The first needs a deployed store's memories, which live in its Postgres volume, so it can enter the tree only as a recorded result. Both depend on `CORTEX_MEMORY_BACKEND` naming a store and `CORTEX_MEMORY_RECALL=judge`, and the cost on `CORTEX_MEMORY_RECALL_POOL_FACTOR` and `DEFAULT_RECALL_K`.
**Verified:** 2026-09-24

The other form of a model reranker: a model that scores a query and a memory as a pair, rather
than a chat completion that orders a numbered list. It needs a scoring-model port, so it is a new
adapter rather than a new policy. It was opened by the ranked-recall close
([R-096](096-ranked-recall-widening.md)), and the geometric relevance floor
([R-101](101-geometric-relevance-floor.md)) later named it as the candidate signal, since it
reads the pair rather than measuring an absolute cosine.

## History

- 2026-08-06: Opened by the ranked-recall close. It was one of the two deferrals that close
  opened and that neither the index cell nor the area header picked up until the arithmetic
  correction later the same day took the area's count from 7 to 9.
- 2026-08-08: Named as the candidate when the geometric relevance floor closed as declined on
  measurement, an absolute cosine having been shown unable to separate the answerable from the
  unanswerable.
- 2026-09-11: Read against the tree; not fired. No cross-encoder or scoring-model port exists:
  `grep -rni 'cross.encoder\|scoring.model' brain/packages/*/src` finds nothing, and the reranker
  surface in `cortex_core` is still the chat-completion judge (`rerank_judge.py`,
  `JudgeRecallPolicy`) over `rerank.py`, `rerank_math.py` and `rerank_policies.py`. The only
  quality reading on record is the wide-corpus one
  ([ranked recall readings](../../readings/ranked-recall.md)), where the judge ties the cosine
  wherever the cosine is right and beats it wherever the cosine is wrong, which is the opposite of
  a shortfall, and it was taken on the widened four-category corpus rather than on a deployed
  store's own memories. No latency budget for the judge exists anywhere in the tree: the turn-cost
  harness measures the judge's extra cost per turn without setting a bound.
- 2026-09-17: Not fired, and neither half was decidable from the tree as the trigger was then
  worded. The grep still finds nothing, no commit since the last reading touched the `rerank`
  modules, the two corpora or their live tests, and nothing ADR-0038 recorded in that time
  mentions the judge. On latency, the turn-cost measurement times a rank at 0.877 s (pool of 20 at
  `DEFAULT_RECALL_K` 5 and `recall_pool_factor` 4) and the turn's first token at +0.515 s against
  the cosine, but no ADR decision or setting states a budget either number could miss. On quality,
  every reading is over notes written for the measurement: the ten inline in
  `brain/packages/inference/tests/test_rerank_judge_live.py`, and the 41 in `recall_corpus.py`
  beside it, read by `test_rerank_judge_wide_live.py` and the turn-cost probe, whose own docstring
  says no real memories were sampled. A real corpus is a deployed store's Postgres volume, which
  no commit contains. The trigger now states both halves in a form a reader can check, and the
  settings they depend on: with the memory backend at its default `none`, or
  `CORTEX_MEMORY_RECALL` set to anything but its default `judge`, the judge never runs and neither
  half can arrive.
- 2026-09-24: Not fired. The grep for a cross-encoder or scoring model still finds nothing, no
  ADR decision or setting states a judge latency budget, and no reading has been taken over a
  deployed store's memories. The earlier line's "no commit touched the `rerank` modules" is no
  longer true: `rerank.py`, `rerank_judge.py` and `rerank_policies.py` now name the turn on each
  recall log line, and the two live tests renamed their variants, with no change to what the judge
  does. One thing moved: the deep phase's judge now asks the deep model (`engines.py`), so the
  0.877 s rank cost describes the cortex judge only, and the trigger now says so.
