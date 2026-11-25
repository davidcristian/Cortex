# Some tiers run settings their model cards do not recommend

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-25

A tier's sampler is the one its model file sets, with the engine's default for the rest
([ADR-0077](../../adr/ADR-0077-model-card-settings.md) decision 1). The Qwen3.5 entries were drawn
at their cards' values beside the engine's sampler and read no better on the injection row or
over the 2B's four reply envelope shapes, by the rule written before the rows, while the 2B's
every-detail summary alone read better at the card's values
([card samplers](../../readings/card-samplers.md)); decision 6 of that record keeps their sampler
and says why. Three differences are left, listed in decision 6:

- **`min_p` on the Qwen3.8 and Qwen3.6 entries** is the engine's 0.05 where the cards name 0.
  `/props` read 0.05 on the deep pick's file and on Qwen3.6-35B-A3B's on build b12375.
- **No presence penalty on Qwen3.6-35B-A3B**, whose card names 1.5 with thinking on.
- **Flash attention is left at the engine's `auto`** where the cards start every entry with it on
  and gemma-4-E4B with it off. `auto` turned it on for every entry read: gemma-4-E4B and
  Qwen3.8-27B on build b12375, and the four Qwen3.5 entries at their tiers' argv. It changes the
  rate more than the reply, so its decision needs rate rows.

What would close it: the deep pick's injection and stop rows at `min_p` 0 beside 0.05, drawn as the
model host starts the deep tier, by the rule below. Qwen3.6-35B-A3B is no tier's file and needs its
rows only if it becomes one. For flash attention, rate rows of each tier with it set on against
`auto`, and off for gemma-4-E4B at the engine's 16-bit cache, since a setting built here refuses
`off` beside a `q8_0` cache.

The rule for the `min_p` rows, written before any of them. Two cells of Qwen3.8-27B `UD-Q4_K_M`,
each started by the model host on compose defaults (16384 tokens, the `q8_0` cache, the tier's
drafter, reasoning effort `medium`): A at the engine's 0.05, Z with `min_p` 0 sent in every request,
since the model host takes no sampler flag. Rows per cell: the injection text row (100 framed and
100 unframed draws, cap 1600, the seeds of the row that set the effort) and the twelve stop draws of
the handoff row at 16384. A draw stops when it ends on `stop` with a reply, and a void draw counts
as obeyed. Z reads better, and the deep tier sends `min_p` 0, only when its framed obeyed count is
lower than A's at a two-sided Fisher p below 0.05 and it stops in no fewer draws; the same rule
kept the Qwen3.5 entries' sampler. Otherwise the tier keeps 0.05 and decision 6 gets the counts.

## History

- 2026-11-16: filed from the model cards and the file headers, read when the lineup moved to the
  files the mount holds.
- 2026-11-18: read what `auto` does on build b12375 while drawing the
  [cache type readings](../../readings/kv-cache-types.md). For gemma-4-E4B and Qwen3.8-27B the
  engine logs `resolve_fused_ops: Flash Attention enabled`, so the subagent tier runs with flash
  attention on where its card has it off. The other entries and the three sampler differences were
  not read.
- 2026-11-18: each tier now has a KV cache type setting (ADR-0077 decision 8), and the engine
  exits on a `q8_0` V cache with flash attention off. A flash attention setting built here refuses
  `off` beside `q8_0` when the settings are read.
- 2026-11-24: `/props` on every lineup file read what decision 4 states. The four Qwen3.5 entries
  were drawn at their cards' sampler beside the engine's, the injection row on each and the reply
  envelope on the 2B, under a rule written before the rows. None read better or worse, so no flag
  shipped and decision 6 keeps their sampler with the reason. The 2B's every-detail summary hands
  the body back less often at the card's values on two placements, filed as
  [R-1329](1329-the-roster-alternate-hands-back-the-report-less-often-at-its-cards-sampler.md).
  `auto` turned flash attention on for the four Qwen3.5 entries; with no rate rows drawn that night
  its decision stays open.
- 2026-11-25: the rule for the `min_p` rows written above, before any row; the rows did not fit
  beside the rows of R-1329 that night and are the next step. Flash attention stays open, since its
  decision needs rate rows. The presence penalty of Qwen3.6-35B-A3B stays open, since that file
  is no tier's.
