# Every tier holds its context in the default 16-bit cache

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-18

No server in the stack starts with `--cache-type-k` or `--cache-type-v`, so each one keeps its
context (the KV cache) in the engine's default type, 16-bit floats. The model baseline of 2026-11-16
was drawn the same way. The engine also accepts an 8-bit type, `q8_0`. The user set the scope of
this task to every model the baseline drew, each with `q8_0` for keys and values.

## What is decided

The rows that decide whether a tier should set the type were drawn on 2026-11-18 on build b12375.
They are in [the cache type readings](../../readings/kv-cache-types.md), with the rule a tier must
meet, which was written before the first row: the engine accepts the type with the tier's flash
attention setting, the tier gains a step of context or 250 MiB, the rate on a filled context stays
at 0.90 of the 16-bit rate or more, and one fixed prompt still gets the same reply in substance.

- **Subagent tier, gemma-4-E4B: does not meet the rule.** With flash attention off, the model
  card's setting, the server exits with `quantized V cache requires flash_attn to be enabled`. With
  the engine's `auto`, which the stack runs, the engine turns flash attention on and accepts the
  type. An 8-bit cache then saves 18 to 43 MiB at the 8K a subagent server runs, and at 64K it
  writes 0.67 to 0.74 of the 16-bit rate. The four small candidates save 7 to 94 MiB at 8K.
- **Chat tier, gemma-4-12B and Qwen3.5-9B: does not meet the rule.** The largest context rises one
  step in every shape the budget decides (beside two subagent servers 160K to 192K for
  gemma-4-12B and 128K to 160K for Qwen3.5-9B, beside one 192K to 256K for Qwen3.5-9B), but on a
  filled context gemma-4-12B writes 0.66 to 0.76 of its 16-bit rate and Qwen3.5-9B 0.67 to 0.90.
- **Deep tier, Qwen3.8-27B: the Q4 file meets the rule, the NVFP4 file does not.** The Q4
  file starts with the type under `auto`. Its largest context with the draft layer rises from 24K
  to 48K (draft length 1 only) and from 40K to 64K without drafting. At 16K and 24K it takes 446
  to 734 MiB less, so every draft length fits at 24K, and it writes 0.97 to 1.00 of the 16-bit
  rate without drafting and at its best draft length. The margin is small at 16K, where draft
  lengths 4 and 5 read 0.84 and 0.88. The NVFP4 file gains the same way (32K to 48K) and writes
  0.81 of its 16-bit rate at 32K and draft length 1.
- **The drafter's cache.** The rows gave the drafter the model's type. Left at 16 bits it changes
  nothing for gemma-4-12B; for the draft layer inside the Qwen3.5-9B file it takes 354 to 556 MiB
  less and is 1.04 times as fast, on one row and three fit checks. The Qwen3.8-27B files, whose
  draft layer is also inside the file, have no row with the draft cache at 16 bits.
- **The reply.** One fixed prompt at temperature 0 gets the same summary in other words from
  gemma-4-12B, Qwen3.5-9B and Qwen3.8-27B. This is an indicator from one prompt per model.

No tier's default changed on 2026-11-18.

## The setting

Each tier has a cache type setting: `CORTEX_KV_CACHE_TYPE`, `CORTEX_KV_CACHE_TYPE_BRAIN` and
`CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU`, each `f16` or `q8_0`, with the rule and its result recorded
in ADR-0077 decision 8. Every default is `f16`, the deep tier's too: the Q4 file that met the
rule is the deep alternate's and the tier ships with no file named, so a deployment that names
that file sets `CORTEX_KV_CACHE_TYPE_BRAIN=q8_0`. A tier at `q8_0` gives its drafter's cache the
same type, as the rows did. A deployment on the NVFP4 file keeps `f16`, because that file does not
meet the rule
([R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)). Step 7
below decides whether a tier that drafts keeps its drafter's cache at 16 bits, since no
Qwen3.8-27B row has the draft cache at 16 bits.

## Rows still to draw

Each command runs in `measurements/model-baseline-2026-11-16/tools/` with the RAM store up
(`HANDOFF.md` there has the two commands) and adds rows to `bench/q8.jsonl`. Afterwards
`python3 q8-redraw.py` draws again every row under the power rule and `python3 q8-report.py`
rebuilds `q8.md`. Together they are about a day of card time.

1. **The chat models at every context**, with whole ladders at 64K, 128K and the largest context
   (on 2026-11-18 the rows at 256K with room for one server were draft lengths 1 and 2 for
   gemma-4-12B and none, 1 and 3 for Qwen3.5-9B):
   `python3 bench3.py --models gemma-4-12B,Qwen3.5-9B --phase chat --reserve-extra 3850 --ladder
   --ctx-list 65536,131072 --kv q8_0 --out q8.jsonl`
2. **The subagent models at every power of two from 4K.** The four that take the type:
   `python3 bench3.py --models gemma-4-E2B,Qwen3.5-4B,Qwen3.5-2B,Qwen3.5-0.8B --phase subagent
   --ladder --min-ctx 4096 --skip-done --kv q8_0 --out q8.jsonl`. gemma-4-E4B only with flash
   attention on, once at 16 bits and once at 8, since its 16-bit rows have it off:
   `python3 bench3.py --models gemma-4-E4B --fa on --phase subagent --ladder --min-ctx 4096
   --skip-done --out q8.jsonl`, then the same with `--kv q8_0`.
3. **The deep tier's two Qwen3.8-27B files where the 16-bit cache has ladders**, the Q4 file at 20K
   and the NVFP4 file at 16K, 20K and 24K:
   `python3 bench3.py --models Qwen3.8-27B,Qwen3.8-27B-NVFP4 --phase deep --ladder --ctx-list
   16384,20480,24576 --skip-done --kv q8_0 --out q8.jsonl`
4. **The split models.** gemma-4-31B does not fit whole at any context and most of what it needs is
   weights, so first the search, which shows whether that still holds:
   `python3 bench3.py --models gemma-4-31B,gemma-4-31B-NVFP4 --phase deep --kv q8_0 --out q8.jsonl`.
   Then split with RAM:
   `python3 bench3.py --models gemma-4-31B,gemma-4-31B-NVFP4 --kind moe --ctx 16384 --phase deep
   --kv q8_0 --out q8.jsonl`, the same with `--ctx 32768`, and
   `python3 bench3.py --models gemma-4-26B-A4B,Qwen3.6-35B-A3B --kind moe --phase deep --kv q8_0
   --out q8.jsonl`.
5. **The CPU rows**, on the CPU image's build b10680:
   `python3 bench3.py --models gemma-4-E4B,Qwen3.5-2B,Qwen3.5-0.8B --kind cpu --phase cpu --kv q8_0
   --out q8.jsonl`. gemma-4-E4B has flash attention off there too, so expect the refusal and draw it
   again with `--fa on`.
6. **Qwen3.8-Flash-Next**, which keeps 7.8 GiB of context on the card at 256K at 16 bits, memory
   its experts could use: `python3 q8-flash.py` (short prompts at 256K, then the ladder on a filled
   32K context, 16 threads).
7. **The drafter's cache at 16 bits beside an 8-bit model cache**, the Qwen files first, since
   their draft layer took less memory that way:
   `python3 bench3.py --models Qwen3.8-27B,Qwen3.8-27B-NVFP4 --phase deep --kv q8_0 --kv-draft f16
   --out q8.jsonl`, and the same flags on the chat command of step 1.
8. **The output check for every model held whole that gets rows**: `python3 q8-output.py <model>`,
   read with `python3 q8-output-report.py --texts`.

What would close it: those rows, the rule applied to every tier in the readings, and the result
recorded in ADR-0077 decision 8. A tier whose shipped file then meets the rule gets `q8_0` as the
default of its setting in `brain/packages/model_manager/src/cortex_model_manager/config.py`.

## History

- 2026-11-17: filed while drawing the model baseline, when the user asked whether its rows used an
  8-bit cache. They did not. The user set the scope to every model and placed it last of three
  follow-ups, after R-1244, so that the baseline run does not grow.
- 2026-11-18: the rule and the rows that decide were written into the readings, then the rows
  were drawn. The deep tier's Q4 file meets the rule and no other tier does. The body was
  rewritten around that result, with the list of rows still to draw for every model.
- 2026-11-18: the setting was built for every tier, each `f16` by default (ADR-0077 decision 8),
  and the task stays open for its rows. Live check on build b12375: the model host started the
  deep tier alone on the Qwen3.8-27B Q4 file at 16K with `--spec-type draft-mtp
  --spec-draft-n-max 3`, no `--model-draft`, and `q8_0` for the model's cache and the drafter's.
  It answered two requests, 175 of 369 drafted tokens were accepted each time, and the card read
  16,969 MiB above its floor of 2,439 MiB at load and 16,995 MiB at the peak. The engine's log
  lines naming the cache type were not read. `shape6.sh` in `~/.cache/cortex-run/2026-11-18/`,
  compose project `cortexn24`, log `logs/deep-q8.txt` there.
