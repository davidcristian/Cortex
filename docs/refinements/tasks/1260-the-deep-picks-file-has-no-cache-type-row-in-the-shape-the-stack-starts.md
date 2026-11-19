# The deep pick's file has no cache type row in the shape the stack starts

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-19

The deep tier's cache type default is `f16`, and for the deep pick's file, gemma-4-31B in Q4, it
is not decided. With an 8-bit cache that file writes 2.08 to 2.11 times its 16-bit rate at 16K
and 32K, on two pairs of launches of one night
([readings](../../readings/kv-cache-every-model.md)). Every one of those rows is split with RAM
by the engine's fit. The stack starts the tier with every layer on the card, and in that shape
the file has one 8-bit row and no 16-bit row.

## How the stack places the deep tier

- `Settings.tiers` in
  [config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py) builds
  the deep tier's `TierArgs` with `ngl` from `CORTEX_NGL_BRAIN` (99 by default, in the settings
  and in `docker/docker-compose.gpu.yml`), the context from `CORTEX_CTX_SIZE_BRAIN` (16384) and
  one slot. Its extra flags are `--cache-ram 0`, the reasoning flags, the drafter at
  `CORTEX_DRAFT_LENGTH_BRAIN` (3) when `CORTEX_MODEL_FILE_BRAIN_DRAFT` names one, and the cache
  type flags.
- `llama_server_argv` in
  [tiers.py](../../../brain/packages/model_manager/src/cortex_model_manager/tiers.py) always
  writes `-ngl` and never writes `--fit` or a thread count. The supervisor starts that argv
  unchanged.
- With `-ngl` named the engine's fit moves no layer. It logs `failed to fit params to free
  device memory: n_gpu_layers already set by user to 99, abort` and keeps every layer assigned
  to the card ([model swap measurements](../../runbooks/model-swap-measurements.md)).

So the tier is never split by the engine. When the file does not fit, the driver spills it into
host RAM and no error is raised, as the same runbook records.

## Whether a deployment can split it

Only by hand. `CORTEX_NGL_BRAIN` takes a layer count, and the rows give the counts the fit chose
under an 18,177 MiB budget: 55 layers at 16 bits and 59 at 8 bits at 16K without the drafter, 53
and 56 with it. No setting passes `--fit on`, which also needs `-ngl` left out, and none passes
the 8 threads the split rows ran with. Whether a fixed `-ngl 59` gives the placement and the rate
the fit gave is an assumption: no row was drawn that way.

## What the rows say about the whole shape

- At 16 bits the engine projects 19,137 MiB for the file at 16K with every layer on the card
  ([the NVFP4 readings](../../readings/nvfp4-deep-tier.md): 19,893 MiB for the NVFP4 file, less
  756 MiB). That is over the 18,177 MiB the readings give a model and under the card's 24,463
  MiB, so whether it fits depends on what the desktop's apps hold. The drafter adds about 1,000
  MiB.
- At 8 bits the file fits whole under the budget at 12K without its drafter, at 18,173 MiB, and
  at no context with it. No 8-bit row exists at 16K with every layer on the card.

## What to draw

The deep tier as the model host starts it, on `gemma-4-31B-it-qat-UD-Q4_K_XL.gguf`, alone on the
card after the swap has stopped the other tiers: the default 16K, every layer on the card, once
without a drafter and once with the pick's drafter at draft length 3, each at `f16` and at
`q8_0` on the same night. `shape6.sh` in `~/.cache/cortex-run/2026-11-18/` started the tier that
way on the Qwen3.8-27B file and is the script to copy. Record the card's highest reading above
its floor, whether the driver spilled into host RAM, and the rate on a filled context.

Then apply the rule of [the first cache type readings](../../readings/kv-cache-types.md). If
neither type runs whole on the card beside the desktop's apps, the decision is a different one:
whether the deep tier gets a setting that lets the engine's fit place it, which needs
`llama_server_argv` to leave `-ngl` out.

What would close it: that draw recorded in the readings, and `CORTEX_KV_CACHE_TYPE_BRAIN`'s
default set from it in `config.py`, or the reason recorded in ADR-0077 decision 8 that it stays
`f16`.

## History

- 2026-11-19: filed when the split rows of gemma-4-31B doubled its rate at 8 bits and the stack
  turned out to start the tier in another shape. Split from
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md), which keeps the
  rows of the other models.
