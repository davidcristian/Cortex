# Every tier holds its context in the default 16-bit cache

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-19

No server in the stack starts with `--cache-type-k` or `--cache-type-v`, so each one keeps its
context (the KV cache) in the engine's default type, 16-bit floats. The model baseline of 2026-11-16
was drawn the same way. The engine also accepts an 8-bit type, `q8_0`. The user set the scope of
this task to every model the baseline drew, each with `q8_0` for keys and values.

## What is decided

The rule a tier must meet was written before the first row, in
[the first cache type readings](../../readings/kv-cache-types.md): the engine accepts the type
with the tier's flash attention setting, the tier gains a step of context or 250 MiB, the rate on
a filled context stays at 0.90 of the 16-bit rate or more, and one fixed prompt still gets the
same reply in substance. [The readings of 2026-11-19](../../readings/kv-cache-every-model.md)
apply it to every model, on build b12375. Each ratio below divides two rows of one night unless
it says otherwise, because the same 16-bit launch read 1.06 to 1.23 times its earlier rate on
2026-11-19 ([R-1259](1259-the-same-launch-reads-a-different-rate-on-another-night.md)).

- **Deep tier, Qwen3.8-27B: the Q4 file meets the rule, the NVFP4 file does not.** At 20K the Q4
  file writes 0.92 of its 16-bit rate without drafting and at draft length 4, its fastest, and
  takes 570 MiB less. Its largest context with the draft layer rises from 24K to 48K. The NVFP4
  file writes 0.93 at 20K and 0.81 at 32K and draft length 1.
- **Deep tier, gemma-4-31B, the pick's Q4 file: not decided.** At 8 bits it fits whole at 12K
  without its drafter, where 16 bits fits at no context. Split with RAM at 16K and 32K the engine
  keeps 59 layers on the card for 55 and 56 for 51, and the file writes 2.08 to 2.11 times its
  16-bit rate without drafting, on two pairs of launches. Card memory does not fall. The stack
  starts the deep tier with every layer on the card, a shape with no pair of rows for this file
  ([R-1260](1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md)).
- **Deep tier, the two MoE files at 256K: do not meet it.** gemma-4-26B-A4B writes 0.69 and
  Qwen3.6-35B-A3B 0.72 of the 16-bit rate without drafting, although more of their weights stay
  on the card.
- **Chat tier: does not meet it.** At 64K gemma-4-12B writes 0.85 without drafting and 0.88 at
  draft length 2. Qwen3.5-9B writes 0.95 and 0.91 at 64K, and 0.67 at 192K and draft length 3
  across two nights, which no night factor read so far brings to 0.90.
- **Subagent tier: does not meet it.** gemma-4-E4B, with the flash attention the engine's `auto`
  turns on, saves 16 to 130 MiB up to 32K and writes 0.87 at 16K and 0.58 at 128K. gemma-4-E2B
  writes 0.83 at 16K. Qwen3.5-4B, Qwen3.5-2B and Qwen3.5-0.8B write 0.98 to 1.01 at 16K, and
  1.11 for Qwen3.5-0.8B at draft length 2, and save 34 to 185 MiB there. At 256K they save 946
  to 2,825 MiB and write 0.87 to 0.92 of the earlier night's 16-bit rate divided by the night
  factor, and 0.78 to 0.89 at their fastest 8-bit draft length before any division. No model
  gains a step of context.
- **The drafter's cache.** Left at 16 bits beside an 8-bit model cache, both Qwen3.8-27B files
  take 82 to 86 MiB less at 48K and write the same rate once the night is divided out. That is
  no gain by the rule, so a tier at `q8_0` keeps giving its drafter the same type.
- **The reply.** One fixed prompt at temperature 0 gets the same summary in other words from
  every model that has rows. This is an indicator from one prompt per model.

## The setting

Each tier has a cache type setting: `CORTEX_KV_CACHE_TYPE`, `CORTEX_KV_CACHE_TYPE_BRAIN` and
`CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU`, each `f16` or `q8_0`, with the rule and its result recorded
in ADR-0077 decision 8. Every default is `f16`, the deep tier's too: the Q4 file that met the
rule is the deep alternate's and the tier ships with no file named, so a deployment that names
that file sets `CORTEX_KV_CACHE_TYPE_BRAIN=q8_0`. A deployment on the NVFP4 file keeps `f16`
([R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)).

## Rows still to draw

Each command runs in `measurements/model-baseline-2026-11-16/tools/` with the RAM store up
(`HANDOFF.md` there has the two commands). 8-bit rows go to `bench/q8.jsonl`.

**Every night draws its own 16-bit pair.** Before the 8-bit rows of a cell, the same launch is
drawn at 16 bits into `bench/q8-ref.jsonl`, without drafting and at one draft length, and the
8-bit rows are divided by that pair only. For a model held whole that is `python3
../q8-probes/ref.py <model> <context> <phase> <room kept>`. For a split model it is the row's own
command without `--kv` and with `--out q8-ref.jsonl`.

1. **The deep tier as the model host starts it, on the pick's file**, gemma-4-31B with every
   layer on the card at both types, is
   [R-1260](1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md).
2. **gemma-4-31B's NVFP4 file split with RAM**, per context, 16384 and then 32768:
   `python3 bench3.py --models gemma-4-31B-NVFP4 --kind moe --ctx 16384 --phase deep --nmax 1
   --out q8-ref.jsonl`, then `python3 bench3.py --models gemma-4-31B-NVFP4 --kind moe --ctx 16384
   --phase deep --kv q8_0 --out q8.jsonl`.
3. **The last draft lengths of Qwen3.6-35B-A3B at 256K.** The 8-bit ladder has lengths 1 to 4
   and its stop rule has not ended it: `python3 bench3.py --models Qwen3.6-35B-A3B --kind moe
   --phase deep --nmax 2 --out q8-ref.jsonl`, then `python3 bench3.py --models Qwen3.6-35B-A3B
   --kind moe --phase deep --kv q8_0 --nmax 4,5,6 --out q8.jsonl`. Length 4 has a row and is
   drawn again so that the stop rule compares rows of one night. Then lengths 1 and 2 again on
   fresh launches (`--nmax 1,2`), since length 1 read 0.93 of the no-draft rate and length 2 read
   1.27, a step the 16-bit ladder does not have.
4. **gemma-4-26B-A4B split with RAM at 32K and 64K**, to see whether its loss at 256K comes with
   the size of the context: the commands of step 2 with `--models gemma-4-26B-A4B` and `--ctx
   32768`, then `--ctx 65536`.
5. **Qwen3.8-27B, the Q4 file, split with RAM at a context it does not hold whole**, to see
   whether the gain of gemma-4-31B's split rows is that file's or any split model's: the commands
   of step 2 with `--models Qwen3.8-27B` and `--ctx 65536`.
6. **A 16-bit pair of the night at 256K for Qwen3.5-2B**, whose rate there reads 0.88 to 0.92
   after division by its two night factors: `python3 ../q8-probes/ref.py Qwen3.5-2B 262144
   subagent 0`, then the 8-bit row again.
7. **The CPU rows**, on the CPU image's build b10680: `python3 bench3.py --models
   gemma-4-E4B,Qwen3.5-2B,Qwen3.5-0.8B --kind cpu --phase cpu --kv q8_0 --out q8.jsonl`.
   gemma-4-E4B has flash attention off there, so expect the refusal and draw it again with
   `--fa on`.
8. **Qwen3.8-Flash-Next**, which keeps 7.8 GiB of context on the card at 256K at 16 bits:
   `python3 q8-flash.py` (short prompts at 256K, then the ladder on a filled 32K context, 16
   threads). The script fixes the 8-bit type and `q8.jsonl`, so its 16-bit rows need a copy with
   `kv=None` and `out="q8-ref.jsonl"`.
9. **The drafter's cache at 16 bits for the chat models**: `python3 bench3.py --models
   gemma-4-12B,Qwen3.5-9B --phase chat --reserve-extra 3850 --ladder --ctx-list 65536,131072
   --kv q8_0 --kv-draft f16 --out q8.jsonl`.
10. **The output check for any model held whole that gets rows then**: `python3 q8-output.py
    <model>`, read with `python3 q8-output-report.py --texts`.

Afterwards `python3 q8-report.py` rebuilds `q8.md`.

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
  A request capped at 300 tokens ended inside the reasoning trace, with 175 of 369 drafted tokens
  accepted. One capped at 3,000 reached its reply and stopped after 2,011 tokens, with 1,406 of
  1,812 drafted tokens accepted. The card read 16,965 MiB above its floor of 2,438 MiB at load
  and 16,991 MiB at the peak. The engine's log at the model host's level has no line naming the
  cache type, so the type was read from the server's argv. `shape6.sh` in
  `~/.cache/cortex-run/2026-11-18/`, compose project `cortexn24`, log `logs/deep-q8-reply.txt`.
- 2026-11-19: every model that has 8-bit rows got a 16-bit row of the same night at one context
  or more, after the same 16-bit launch read 1.06 to 1.23 times its earlier rate. The Q4 file of
  Qwen3.8-27B still meets the rule, at 0.92 of the 16-bit rate; no other file held whole does.
  gemma-4-31B split with RAM writes 2.08 to 2.11 times its 16-bit rate, a shape the stack does
  not start, so the deep pick's file is not decided. The body was rewritten around the new
  readings, with the rows that are left. No default changed. R-1259 filed for the difference
  between nights and R-1260 for the deep pick's file.
