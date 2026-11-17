# Every tier holds its context in the default 16-bit cache

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-17

No server in the stack starts with `--cache-type-k` or `--cache-type-v`, so each one keeps its
context (the KV cache) in the engine's default type, 16-bit floats. The model baseline of 2026-11-16
was drawn the same way: none of its launches set a cache type, so every largest context it reports
is a 16-bit figure. The model cards recorded in ADR-0077 name no cache type.

The engine also accepts an 8-bit type, `q8_0`, which takes about half the memory per token of
context. Whether a tier should use it has not been measured.

What the context costs at 16 bits, measured 2026-11-16 on the 24 GB card with every layer on the
card:

- gemma-4-12B grows by 3,230 MiB between a 64K and a 256K context.
- Qwen3.5-9B grows by 4,250 MiB between 64K and 192K.
- Qwen3.8-27B grows by 1,560 MiB between 16K and 40K.
- Qwen3.8-Flash-Next keeps 7.8 GiB of context on the card at 256K, memory its experts could use.

The results an 8-bit cache could change, each a largest context that the 18,177 MiB model budget
decides today:

- gemma-4-12B beside two gemma-4-E4B servers: 160K with its drafter.
- Qwen3.5-9B beside one gemma-4-E4B server: 192K with its draft layer, 256K only without it.
- Qwen3.8-27B alone: 24K with its draft layer up to draft length 3, 40K without it.
- gemma-4-31B: it does not fit whole at any context, and most of what it needs is weights, so an
  8-bit cache is unlikely to change that.

What is not known, and must be measured before a tier changes:

- The rate per token with an 8-bit cache, with and without a drafter.
- Whether the output changes.
- Whether the engine accepts an 8-bit cache with flash attention off, which is the setting the
  gemma-4-E4B card recommends and the subagent tier runs.

What would close it: a second set of baseline rows with `q8_0` for both keys and values, for every
model the baseline drew and for the NVFP4 files of
[R-1244](1244-the-nvfp4-files-for-the-deep-tier-have-no-baseline-rows.md) once those have their
16-bit rows. The rows are drawn the way the 16-bit rows were (the same budget, the same top-down
search for the largest context, the same draft ladder and stop rule), with a check of the
gemma-4-E4B case first. Then a decision is recorded in ADR-0077. If a tier is to set a cache type,
that is a setting per tier in `tiers()` in
`brain/packages/model_manager/src/cortex_model_manager/config.py` and in the compose files, which
`flagcheck.py` and `settingscheck.py` then read.

## History

- 2026-11-17: filed while drawing the model baseline, when the user asked whether its rows used an
  8-bit cache. They did not. The user set the scope to every model and placed it last of three
  follow-ups, after R-1244, so that the baseline run does not grow.
