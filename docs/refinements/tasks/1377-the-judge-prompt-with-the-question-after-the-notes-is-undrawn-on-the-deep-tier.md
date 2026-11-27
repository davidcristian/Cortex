# The judge prompt with the question after the notes is undrawn on the deep tier

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-11-27

During a handoff the deep model answers the recall judge too. Since 2026-11-27 the judge's prompt
puts the question after the notes and tells the model that a note sharing only the question's words
does not help; it passed its rule on the cortex alone
([readings](../../readings/ranked-recall.md#a-number-asked-to-keep-over-stored-exchanges)). On
2026-09-28 the old prompt drew 24 of 26 correct on the wide corpus on Qwen3.8-27B, the deep pick,
with both misses on `ABSENT` questions.

## What to do

1. Write the rule first: the new prompt reads apart from that 24 of 26 at 20 or fewer (two-sided
   Fisher, p below 0.05), the measure of the 2026-09-28 reading. Then draw
   `test_rerank_judge_wide_live.py` and `test_rerank_judge_exchanges_live.py` against the deep tier
   started by the model host on compose defaults, Q4 file, with every other tier stopped. Counts
   only; no rate.
2. A result apart from 24 of 26, or an exchanges count under 10 of 20, goes into this task as the
   next step; the prompt is not changed on a deep-tier reading alone.

## History

- 2026-11-27: filed from task 1312, whose judge change was drawn on the cortex only.
