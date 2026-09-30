# Measure whether the deep tier's 16384 context slows decode

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** inference
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

On 2026-09-30 the deep pick at `--ctx-size 16384` decoded the same tokens as its 2026-09-26 stop
row at 8192 at 0.86 of that row's rate (0.83 to 0.92 over the eleven draws both rows finished),
where 1.0 (0.95 to 1.05) was predicted ([history window
readings](../../readings/history-window.md#the-deep-tier-at-16384)). The two rows were drawn on
different nights. The SM clock and the enforced power limit do not account for the gap, and
neither row recorded the memory clock. If the context costs decode, a handoff decodes about a
seventh slower than the 8192 figures the deep candidates were compared on, a cost ADR-0014
decision 8 does not state.

Written down before the replication is drawn:

1. **One measurement session with the loads alternating** 8192, 16384, 8192, 16384, each the
   tier's argv with only `--ctx-size` changed. Each load draws the stop row's Q1 and Q3 at seeds
   101 to 103 and 301 to 303, which gave the same tokens at both contexts, with
   `clocks.current.memory` added to the clock sampler's fields. The drivers of the 2026-09-30 row
   (`deeplib.tier_argv(..., ctx=...)` and `questions.body`) build both. About 30 minutes on the
   card.
2. **The deciding reading** is each 16384 load's median rate over the six draws against the same
   draws on the 8192 loads beside it. If the context costs decode it reads 0.86 (0.80 to 0.93) on
   both; the null result is 0.97 to 1.03 on both, which puts the gap on the card's state that
   night.
3. **If it replicates**, the cost goes into ADR-0014 decision 8 beside the stop count, and one load
   at each context with `-lv 4` records the buffers each allocates.

## History

- 2026-09-30: filed by R-736's stop row at 16384, whose decode prediction did not hold.
