# The deep pick's file has no cache type row in the shape the stack starts

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-20

The deep tier's cache type default is `f16`. For the deep pick's file, gemma-4-31B in Q4, the rows
that decide it were missing in the shape the stack starts: every layer on the card. They were
drawn on 2026-11-20, twice, and the file meets the rule of
[the first cache type readings](../../readings/kv-cache-types.md) in that shape
([readings](../../readings/kv-cache-deep-whole.md)). The default is not changed yet. What is left
is that change, and a second question the draw opened: neither type fits the budget at 16K.

## The draw

- **File of rows**: `measurements/model-baseline-2026-11-16/bench/deep-whole-2026-11-20.jsonl`,
  which git ignores. Lines 1 to 4 are the first draw, lines 5 to 8 the second, every row of
  2026-11-20 on engine build b12375. `python3 q8-probes/dw2.py` there prints both.
- **Shape**: the model host started from the repo's compose files on
  `gemma-4-31B-it-qat-UD-Q4_K_XL.gguf`, every deep setting at its default (16K, `-ngl 99`, one
  slot), the cortex stopped first. Per draw four launches: `f16` and `q8_0` without a drafter,
  then both with `mtp-gemma-4-31B-it-Q8_0.gguf` at draft length 3. A `q8_0` launch has
  `--cache-type-k q8_0 --cache-type-v q8_0` in its argv, and with the drafter the two
  `-draft` flags too.
- **Rate**: 256 tokens written after a prompt of 15,896 tokens, the median of seeds 7, 8 and 9.

| draw | drafter | rate, `q8_0` over `f16` | prompt pass | highest reading above the floor, `f16` and `q8_0` |
| --- | --- | --- | --- | --- |
| first | none | 0.913 | 1.026 | 18,742 and 18,384 MiB |
| first | length 3 | 1.035 | 1.058 | 19,538 and 19,084 MiB |
| second | none | 0.912 | 1.036 | 19,443 and 18,375 MiB |
| second | length 3 | 1.018 | 1.081 | 19,774 and 19,086 MiB |

The first draw's two `f16` rows understate their memory: the card moved 701 and 297 MiB of the
desktop's memory off itself under them, and with that added they read 19,443 and 19,835 MiB. The
pass mark of the second draw was written before its first launch (0.90 or more and 250 MiB or
more less, in both drafter settings) and was met.

## The rule, item by item

1. **Accepted: met on the argv.** All four `q8_0` launches start and reach `ready`, with no
   flash attention flag, which is the engine's `auto`. The model host's log at its level has no
   line naming the cache type, so the type was read from the server's argv and not from the log.
2. **Gain: met.** At draft length 3, the length the tier ships with, the highest reading is 454
   and 688 MiB lower; without the drafter 358 and 1,068 MiB lower. The rule asks for 250.
3. **Rate: met, by 0.012 without drafting.** 0.913 and 0.912 without the drafter, 1.035 and 1.018
   at draft length 3, prompt pass 1.03 to 1.08. The rule asks for 0.90. One fixed launch drawn
   eight times that night spread by 0.034, so one launch per row cannot tell 0.912 from 0.90; the
   two draws agree to 0.001. Only draft length 3 was drawn.
4. **Output: passes.** At 8K with every layer on the card the 8-bit reply to the fixed prompt is
   the 16-bit reply token for token, 119 of 119 (rows 32 to 34 of `bench/q8-output.jsonl`).

## What the change of the default touches

- The default of the `CORTEX_KV_CACHE_TYPE_BRAIN` setting in
  [config.py](../../../brain/packages/model_manager/src/cortex_model_manager/config.py), which
  is `ENGINE_KV_CACHE_TYPE` today, the same variable in `docker/docker-compose.gpu.yml`, and
  ADR-0077 decision 8, which says every tier's default is the engine's 16 bits.
- The default applies to whatever file a deployment names. Both Q4 files meet the rule (the
  pick's here, the Qwen3.8-27B alternate's in
  [the rows of 2026-11-19](../../readings/kv-cache-every-model.md)). The NVFP4 file of
  Qwen3.8-27B does not, at 0.81 at 32K and draft length 1, and the NVFP4 file of gemma-4-31B has
  no row held whole, so a deployment on either NVFP4 file would set `f16`
  ([R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)).
- The figures above are audited against the row file before the default moves.

## What the draw leaves open

- **Neither type fits the budget at 16K.** With the desktop's apps counted as 4,750 MiB and 1,536
  MiB kept free, models get 18,177 MiB. `q8_0` is over it by 198 to 207 MiB without the drafter
  and 907 to 909 MiB with it; `f16` by 1,266 MiB and 1,597 MiB in the second draw. Every row ran
  whole on the card because the desktop's apps held 3,221 to 4,247 MiB. At 8 bits the file fits
  the budget whole at 12K without its drafter and at no context with it.
- **`f16` with the drafter is at the card's limit**: 23,085 and 23,057 MiB of 24,463 at the
  highest reading, with about 310 MiB of the launch not accounted for on the card in the second
  draw. Its rate is not a spill's (0.97 and 0.98 of the `q8_0` row), and a small spill is not
  ruled out.
- **How the stack places the tier.** `llama_server_argv` in
  [tiers.py](../../../brain/packages/model_manager/src/cortex_model_manager/tiers.py) always
  writes `-ngl` (99 from `CORTEX_NGL_BRAIN`) and never `--fit` or a thread count, so the engine
  moves no layer and a tier that does not fit spills into host RAM with no error
  ([model swap measurements](../../runbooks/model-swap-measurements.md)). Split by the engine's
  fit the same file writes 2.08 to 2.11 times its 16-bit rate at 8 bits, a shape no setting
  reaches.

## Rows not drawn

Each launch is `python3 q8-probes/deepwhole.py <label> f16|q8_0 none|mtp [note]` in
`measurements/model-baseline-2026-11-16/`, with the stack files of
`~/.cache/cortex-run/2026-11-20/` (compose project `cortexn25`); `bash
~/.cache/cortex-run/2026-11-20/deep-stop.sh` removes the project afterwards.

1. The drafted pair at 8K, where neither type is at the card's limit, to see whether `f16` keeps
   the 1.10 lead it has without the drafter.
2. The four launches with the desktop's apps at 4,750 MiB or more, the load the budget counts.

What would close it: `CORTEX_KV_CACHE_TYPE_BRAIN`'s default set from the readings, or the reason
recorded in ADR-0077 decision 8 that it stays `f16`; and the question of the tier's context or
placement at 16K either decided or filed as its own task.

## History

- 2026-11-19: filed when the split rows of gemma-4-31B doubled its rate at 8 bits and the stack
  turned out to start the tier in another shape. Split from
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md), which keeps the
  rows of the other models.
- 2026-11-20: the draw was made, twice, each of four launches through the model host. The file
  meets the rule in the shape the stack starts: 0.913 and 0.912 of the 16-bit rate without the
  drafter, 1.035 and 1.018 at draft length 3, 454 and 688 MiB less with the drafter, the same
  reply. No row fits the 18,177 MiB budget at 16K at either type. The body was rewritten around
  the draw; the default is left for its own change.
