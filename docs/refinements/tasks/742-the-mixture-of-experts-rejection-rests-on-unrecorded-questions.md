# The mixture-of-experts rejection rests on unrecorded questions

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-28

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

**Written 2026-09-28, before the draw.** Each entry draws the stop row's twelve draws on the card at
the deep tier's argv under the model host's caps, on the image the pick's row used
(`sha256:952424b09abc`), with the drivers in `measurements/deep-2026-09-26/q27-drivers/` copied into
the unattended run logged at `measurements/sitting-2026-09-28/` (`742g26.log`, `742q35.log`). The
Qwen entry is drawn at `UD-Q3_K_XL`, the quant on the mount nearest the rejected `UD-Q3_K_M` and the
one the switch probe read; `UD-Q4_K_M` is 22.13 GB and is not drawn.

Deciding, as the stop rows decide: draws ending on `stop` with a non-empty reply before the context
fills, of 12, against the pick's 11 by a two-sided Fisher test, apart at 5 or fewer. If either entry
is not apart, decision 8's reason is rewritten on this row, since that entry then stops as often as
the pick on recorded questions; if both are apart below, decision 8 cites this row in place of the
unrecorded one. Right by hand is read beside it and decides nothing. Predicted stopped:
gemma-4-26B-A4B 8 (4 to 12) and Qwen3.6-35B-A3B 7 (3 to 11), neither apart. Priced at 1200 s each
with its load.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-28: premise checked: both entries are on the mount and fit the card alone, and the stop
  row's drivers take any artifact, so the row needs the card and no new code. The rule and the
  predictions are written above before the draw.
