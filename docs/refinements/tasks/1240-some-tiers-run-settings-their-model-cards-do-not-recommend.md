# Some tiers run settings their model cards do not recommend

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-27

A tier's sampler is the one its model file sets, with the engine's default for the rest
([ADR-0077](../../adr/ADR-0077-model-card-settings.md) decision 1). The Qwen3.5 entries were drawn
at their cards' values beside the engine's sampler and read no better on the injection row or
over the 2B's four reply envelope shapes, and the deep pick read no better at its card's `min_p`
of 0 on its injection row and its stop draws behind a full handoff prompt, each by a rule written
before the rows ([card samplers](../../readings/card-samplers.md)); decision 6 of that record keeps
those samplers and says why. Three differences are left, listed in decision 6:

- **`min_p` on Qwen3.8-Flash-Next and Qwen3.6-35B-A3B** is the engine's 0.05 where the cards name
  0. `/props` read 0.05 on Qwen3.6-35B-A3B's file on build b12375.
- **No presence penalty on Qwen3.6-35B-A3B**, whose card names 1.5 with thinking on.
- **Flash attention is left at the engine's `auto`** where the cards start every entry with it on
  and gemma-4-E4B with it off. `auto` turned it on for every entry read: gemma-4-E4B and
  Qwen3.8-27B on build b12375, and the four Qwen3.5 entries at their tiers' argv. It changes the
  rate more than the reply, so its decision needs rate rows.

What would close it: for flash attention, rate rows of each tier with it set on against `auto`,
and off for gemma-4-E4B at the engine's 16-bit cache, since a setting built here refuses `off`
beside a `q8_0` cache. Qwen3.8-Flash-Next and Qwen3.6-35B-A3B are no tier's file and need their
sampler rows only if one becomes a tier's, drawn as the deep pick's were.

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
- 2026-11-25: the rule for the `min_p` rows written into this task, before any row; the rows did
  not fit beside the rows of R-1329 that night and are the next step. Flash attention stays open,
  since its decision needs rate rows. The presence penalty of Qwen3.6-35B-A3B stays open, since
  that file is no tier's.
- 2026-11-26: the `min_p` rows drawn on the deep pick as the model host starts it with its draft
  layer, by the rule this task stated on 2026-11-25, which the
  [readings](../../readings/card-samplers.md#the-deep-pick-at-min_p-0) quote. At `min_p` 0 the pick
  obeyed 0 of 100 framed draws against 0 at 0.05 (two-sided Fisher p 1) and stopped on 11 of 12
  against 11, so the tier keeps 0.05 and decision 6 has the counts. Flash attention and the
  Qwen3.6 presence penalty stay open.
- 2026-11-27: no tier names a flash attention flag
  (`test_no_tier_names_a_flash_attention_setting_so_an_8_bit_cache_is_never_refused`), and no
  tier names Qwen3.8-Flash-Next or Qwen3.6-35B-A3B, so the premise holds. The flash attention rows
  wait on rate rows, since the card's power limit read 175, not the baseline's 155.
