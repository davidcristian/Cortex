# The mixture-of-experts rejection rests on unrecorded questions

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-26

Decision 8 rejects the two mixture-of-experts deep entries, Qwen3.6-35B-A3B and gemma-4-26B-A4B,
because on 2026-08-04 they spent the whole 8192 context reasoning and returned an empty reply
([model lineup](../../readings/model-lineup.md)). That reading was taken on build `b10236`, and its
four questions are recorded nowhere, so neither the empty replies nor the answered counts (1 of 4
and 0 of 4) can be drawn again. The A3B quant it names, `UD-Q3_K_M`, is no longer on the mount,
which holds `UD-Q3_K_XL` and `UD-Q4_K_M`; the injection harness names the second.

Since 2026-09-26 the stop row has four written questions and the pick's count on them, 11 of 12 on
`b10680` ([deep candidates](../../readings/deep-candidates.md#the-stop-rows)). What would close it:
each mixture-of-experts entry on those 12 draws at the deep tier's argv and the same build, its
prediction written here first. A draw that fills the context takes about 80 s at 2.6 times the
pick's decode rate, so each row costs at most about 20 card minutes with its load. If either stops
as often as the pick, the axis decision 8 rejects them on needs reading again; if neither does, the
rejection rests on a recorded row.

## History

- 2026-09-26: filed by the deep candidates' measurement.
