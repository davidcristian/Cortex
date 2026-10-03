# A cross-encoder rank

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Trigger:** a reading in `docs/readings/ranked-recall.md` taken over memories nobody wrote for the
measurement (neither the ten notes inline in `test_rerank_judge_live.py` nor the 41 in
`recall_corpus.py`) in which the judge drops an answerable note the cosine kept or ranks it lower;
or a first-token or whole-turn latency bound, in an ADR decision or a setting, that the judge's
recorded cost exceeds: a rank at `k` 5 over a pool of 20 costs 0.877 s, and a judged turn's first
token comes 0.539 s after a raw one's.
**Verified:** 2026-10-03

The other form of a model reranker: a model that scores a query and a memory as a pair, rather than
a chat completion that orders a numbered list. It was opened by the ranked-recall close
([R-096](096-ranked-recall-widening.md)), and the geometric relevance floor
([R-101](101-geometric-relevance-floor.md)) later named it as the candidate signal, since it reads
the pair rather than measuring an absolute cosine.

Building it takes four parts: a scoring port beside `InferenceBackend`, whose one call is a streamed
completion; an adapter for it, which the engine already offers (the cached `server` image, build
10680, lists `--rerank`); a reranker model, of which the model mount's 73 GGUF files hold none; and
a policy beside `JudgeRecallPolicy` that calls the port.

Both halves of the trigger need the judge to run: `CORTEX_MEMORY_BACKEND` naming a store (the code
default is `none`, and `docker-compose.memory.yml` sets `pgvector`) and `CORTEX_MEMORY_RECALL` at
its default `judge`. A deployed store's memories live in its Postgres volume, so the first half can
reach the tree only as a recorded reading. The recall trail (`CORTEX_MEMORY_RECALL_AUDIT_FILE`)
keeps each recall's kept and dropped ids with their cosine scores, but never the query or a text, so
judging which note was answerable still needs the store. The cost figures are the cortex judge's;
the deep phase's judge asks the deep model, where a recall cost 0.89 s at `k` 3 over a pool of 12.

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
- 2026-10-03: Not fired. The search for a cross-encoder or scoring model in `brain/packages/*/src`
  still finds nothing, every judge reading in the ranked recall record is still over the two written
  corpora (the 2026-09-28 rows on the Qwen deep candidates reuse the 41 notes), and no ADR decision
  or setting bounds a turn's first token or whole turn below minutes: the shortest such bound is the
  cortex client's read stall, `CORTEX_INFERENCE_STALL_TIMEOUT_S` at 120 s, against a judge cost
  under a second. Three corrections. The trigger cited the 2026-08-08 first-token cost of 0.515 s,
  where the later A/B/A run of 2026-08-09 recorded 0.539 s. The deep judge's 0.89 s is a recall's
  cost, not a rank's. And the build needs a reranker model as well as a port and an adapter, since
  the mount holds none. The settings the trigger listed moved into the text, beside the recall
  trail, which now records judged recalls without their texts.
