# A Qwen tier at q8_0 gives its draft layer a cache that takes more memory

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-20

`cache_flags` in
[tiers.py](../../../brain/packages/model_manager/src/cortex_model_manager/tiers.py) gives a
tier's drafter the cache type of its model: a tier at `q8_0` that drafts also gets
`--cache-type-k-draft q8_0 --cache-type-v-draft q8_0`. For Qwen3.5-9B, which drafts with a layer
inside its own file, the server takes more memory that way than with the drafter's cache left at
16 bits, at the same rate. An 8-bit cache is the smaller type, so the direction is not explained.

## Reproduction

On 2026-11-20, build b12375, chat phase with room for one subagent server, the model's cache at
`q8_0`, draft length 3, each row on a fresh launch
([readings](../../readings/kv-cache-remaining-cells.md)): `bash q8-probes/chain35.sh` under
`measurements/model-baseline-2026-11-16/`, which git ignores, draws the 128K pair.

| context | memory at load, drafter cache `f16` | drafter cache `q8_0` | rate, `f16` over `q8_0` |
| --- | --- | --- | --- |
| 64K | 7,409 MiB | 7,559 MiB | 1.004 |
| 128K | 9,137 MiB | 9,423 MiB | 0.955 |
| 128K, second pair | 9,131 MiB | 9,423 MiB | 1.036 |

The second pair at 128K was drawn with its pass mark written first and met it. gemma-4-12B,
which drafts with a separate file, loads the same memory at both drafter cache types at 64K and
128K. Both Qwen3.8-27B files take 82 to 86 MiB less at 48K with the drafter's cache at 16 bits.

## What to do

1. Find where the memory goes: read the engine's memory breakdown lines of both launches at
   128K and compare the context and compute columns.
2. If the difference is the engine's, a tier at `q8_0` on a Qwen file should leave its drafter's
   cache at 16 bits. That needs `cache_flags` to take the drafter's type on its own, and a
   setting or a rule per file.

No tier ships at `q8_0` with a Qwen draft layer today: the chat tier does not meet the rule of
[the first cache type readings](../../readings/kv-cache-types.md), and the deep tier ships with
no file named. Its default is `q8_0` (ADR-0077 decision 8), so a deployment that names the
Qwen3.8-27B Q4 file and drafts with its layer pays 82 to 86 MiB at 48K. The 570 MiB the type
saves that file at 20K was read with the drafter's cache at 8 bits.

What would close it: the cause recorded in the readings, and either the drafter's type set on
its own for the files it helps or the reason recorded that it follows the model's.

## History

- 2026-11-20: filed when the rows of
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md) showed 286 and 292
  MiB less for Qwen3.5-9B at 128K with the drafter's cache at 16 bits.
