# Some tiers run settings their model cards do not recommend

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-16

A tier's sampler is the one its model file sets, with the engine's default for the rest
([ADR-0077](../../adr/ADR-0077-model-card-settings.md) decision 1). The gemma files set their
card's temperature, `top_p` and `top_k`, so the three picks already run them. Four differences are
left, read from the file headers and the cards on 2026-11-16 and listed in decision 6 of that
record:

- **The Qwen3.5 files set no sampler.** The 0.8B, 2B, 4B and 9B headers have no `general.sampling`
  key, so those entries run the engine's temperature 0.8 and `top_k` 40 where their cards name 1.0
  and 20. The cortex alternate and the roster alternate are among them.
- **`min_p` on every Qwen entry** is the engine's 0.05 where the cards name 0.
- **No presence penalty is set** where the Qwen3.5 and Qwen3.6 cards name 1.5 to 2.0.
- **Flash attention is left at the engine's `auto`** where the cards start every entry with it on
  and gemma-4-E4B with it off.

What would close it: `/props` read on each entry's file to confirm what the server runs, then the
injection rows and the reply envelope of the Qwen3.5 entries drawn at their cards' values beside
the engine's. A tier that reads better gets the setting as a flag on its server, and one that does
not gets the reason written into decision 6.

## History

- 2026-11-16: filed from the model cards and the file headers, read when the lineup moved to the
  files the mount holds.
