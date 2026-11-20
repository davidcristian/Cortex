# Every tier holds its context in the default 16-bit cache

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-20

The cortex and the subagent servers start without `--cache-type-k` or `--cache-type-v`, so each
keeps its context (the KV cache) in the engine's default type, 16-bit floats. The model baseline of
2026-11-16 was drawn that way for every tier. The engine also accepts an 8-bit type, `q8_0`, which
the deep tier runs by default since 2026-11-20. The user set the scope of this task to every model
the baseline drew, each with `q8_0` for keys and values.

## What is decided

The rule a tier must meet was written before the first row, in
[the first cache type readings](../../readings/kv-cache-types.md): the engine accepts the type
with the tier's flash attention setting, the tier gains a step of context or 250 MiB, the rate on
a filled context stays at 0.90 of the 16-bit rate or more, and one fixed prompt still gets the
same reply in substance. It is applied on build b12375 in
[the readings of 2026-11-19](../../readings/kv-cache-every-model.md),
[the readings of 2026-11-20](../../readings/kv-cache-remaining-cells.md) and
[the deep tier's own draw](../../readings/kv-cache-deep-whole.md). Each ratio below divides two
rows of one night, because the same 16-bit launch reads a different rate on another night
([R-1259](1259-the-same-launch-reads-a-different-rate-on-another-night.md)).

- **Deep tier, gemma-4-31B, the pick's Q4 file: meets the rule in the shape the stack starts.**
  With every layer on the card at 16K it writes 0.913 and 0.912 of its 16-bit rate without the
  drafter and 1.035 and 1.018 at draft length 3, takes 454 and 688 MiB less with the drafter, and
  gives the same reply token for token. The engine's log at level 4 names `q8_0` for its caches
  and its drafter's. The tier's default is `q8_0` on these rows (ADR-0077 decision 8).
  Neither type fits the 18,177 MiB budget there
  ([R-1264](1264-the-deep-tier-at-16k-is-over-the-model-budget-with-every-layer-on-the-card.md)).
  Split with RAM the file writes 2.08 to 2.11 times its 16-bit rate, a shape the stack does not
  start.
- **Deep tier, gemma-4-31B, the NVFP4 file: not decided.** It is held whole at no context. Split
  with RAM it writes 1.52 and 1.56 times its 16-bit rate at 16K and 1.94 times at 32K, with 3 to
  4 more layers on the card and no fall in card memory. It has no output check.
- **Deep tier, Qwen3.8-27B: the Q4 file meets the rule, the NVFP4 file does not.** At 20K the Q4
  file writes 0.92 of its 16-bit rate without drafting and at draft length 4, and takes 570 MiB
  less. Its largest context with the draft layer rises from 24K to 48K. At 64K, where 16 bits
  must split and 8 bits is whole without the drafter, it writes 4.25 and 4.32 times the 16-bit
  rate, and 2.71 times at draft length 1: upper readings, drawn with allowances given by hand.
  The NVFP4 file writes 0.93 at 20K and 0.81 at 32K and draft length 1.
- **Deep tier, the two MoE files: do not meet it.** Qwen3.6-35B-A3B at 256K writes 0.73 of the
  16-bit rate without drafting and 0.83 at draft length 2; its 8-bit ladder is ended by the stop
  rule at length 6. gemma-4-26B-A4B writes 0.69 at 256K split with RAM, and held whole 0.829 and
  0.848 at 32K and 0.720 and 0.757 at 64K, so its loss does not come with the split.
- **Chat tier: does not meet it.** Without drafting gemma-4-12B writes 0.855 at 64K and 0.745 at
  128K, and Qwen3.5-9B 0.961 and 0.955. At draft length 3 Qwen3.5-9B writes 0.885 at 64K and
  0.775 at 128K.
- **GPU subagent tier: does not meet it.** gemma-4-E4B, with the flash attention the engine's
  `auto` turns on, saves 16 to 130 MiB up to 32K and writes 0.87 at 16K and 0.58 at 128K.
  gemma-4-E2B writes 0.83 at 16K. Qwen3.5-4B, Qwen3.5-2B and Qwen3.5-0.8B write 0.98 to 1.01 at
  16K and save 34 to 185 MiB there. At 256K Qwen3.5-2B saves 948 MiB and writes 0.917 without
  drafting and 0.813 at draft length 2. No model gains a step of context.
- **CPU subagent servers: do not meet it.** The cache is in host RAM, so no card memory is
  saved. gemma-4-E4B does not start at 8 bits with flash attention off, its card's setting; with
  it on, 8 bits writes 0.875 of what the server ships with. The two Qwen files write 1.007 and
  1.000 at 8K with the prompt pass at 0.75 and 0.62, and at 16K and 32K 1.07 to 1.24 with the
  prompt pass at 0.24 to 0.63.
- **The drafter's cache.** Left at 16 bits beside an 8-bit model cache it changes nothing for
  gemma-4-12B and takes 82 to 86 MiB less for both Qwen3.8-27B files at 48K. For Qwen3.5-9B it
  takes 150 MiB less at 64K and 286 and 292 MiB less at 128K, at the same rate
  ([R-1263](1263-a-qwen-tier-at-q8-0-gives-its-draft-layer-a-cache-that-takes-more-memory.md)).
- **The reply.** One fixed prompt at temperature 0 gets a reply that ends on its own and does
  not repeat itself from every model that has rows held whole. gemma-4-31B's is the same token
  for token. The clauses that differ for four other models on 2026-11-20 are still to be read
  against the prompt (step 7 below). This is an indicator from one prompt per model.

## The setting

Each tier has a cache type setting: `CORTEX_KV_CACHE_TYPE`, `CORTEX_KV_CACHE_TYPE_BRAIN` and
`CORTEX_KV_CACHE_TYPE_SUBAGENT_GPU`, each `f16` or `q8_0`, with the rule and its result recorded
in ADR-0077 decision 8. The deep tier's default is `q8_0`, set on 2026-11-20 from the draw
above, and a deployment that names an NVFP4 deep file sets `CORTEX_KV_CACHE_TYPE_BRAIN=f16`
([R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)). The cortex's and the subagent servers' defaults are `f16`.

## Rows still to draw

Each command runs in `measurements/model-baseline-2026-11-16/tools/` with the RAM store up
(`HANDOFF.md` there has the two commands). 8-bit rows go to `bench/q8.jsonl`.

**Every night draws its own 16-bit pair.** Before the 8-bit rows of a cell, the same launch is
drawn at 16 bits into `bench/q8-ref.jsonl`, without drafting and at one draft length, and the
8-bit rows are divided by that pair only. The night's first and last launch is `python3
../q8-probes/drift.py` (R-1259).

1. **Qwen3.8-Flash-Next**, the one whole model left. It keeps 7.8 GiB of context on the card at
   256K at 16 bits: `python3 q8-flash.py` (short prompts at 256K, then the ladder on a filled 32K
   context, 16 threads). The script fixes the 8-bit type and `q8.jsonl`, so its 16-bit rows need
   a copy with `kv=None` and `out="q8-ref.jsonl"`, run first. Staging the file empties the RAM
   store.
2. **Qwen3.6-35B-A3B at 8 bits and draft length 3**, the fastest length on 2026-11-19, which has
   no row beside a pair of its night: `python3 bench3.py --models Qwen3.6-35B-A3B --kind moe
   --phase deep --nmax 2 --out q8-ref.jsonl`, then the same with `--kv q8_0 --nmax 3 --out
   q8.jsonl`.
3. **The CPU rows with a drafter at 16K and 32K, and the other draft lengths at 8K**: `python3
   bench3.py --models gemma-4-E4B,Qwen3.5-2B,Qwen3.5-0.8B --kind cpu --phase cpu --ctx 16384
   --out q8-ref.jsonl`, then the same with `--kv q8_0 --out q8.jsonl`, and for gemma-4-E4B both
   again with `--fa on`; then `--ctx 32768`, and no `--ctx` for 8K. Three cells get no filled
   pass until
   [R-1262](1262-the-benchmark-drivers-cap-leaves-three-cpu-cells-without-a-filled-pass.md) is
   done.
4. **The Qwen3.5-0.8B CPU pair at 32K once more**, since 1.242 is one launch each: `python3
   ../q8-probes/cpurow.py Qwen3.5-0.8B 32768 f16 on`, then the same with `q8_0`.
5. **16-bit rows at the fastest 8-bit draft lengths.** gemma-4-26B-A4B at draft length 2:
   `python3 bench3.py --models gemma-4-26B-A4B --kind moe --ctx 32768 --phase deep --nmax 2 --out
   q8-ref.jsonl`, then the same with `--kv q8_0 --out q8.jsonl`, then both with `--ctx 65536`.
   Qwen3.8-27B at 64K at lengths 2 and 3: `python3 ../q8-probes/splitrow.py Qwen3.8-27B 65536 f16
   row <length> 600 <note>`.
6. **Qwen3.8-27B at 64K through the driver's own search**, and its 16-bit no-draft placement one
   step larger, once
   [R-1261](1261-the-benchmark-drivers-allowance-search-can-end-on-a-placement-that-does-not-fit.md)
   is done: `python3 bench3.py --models Qwen3.8-27B --kind moe --ctx 65536 --phase deep --nmax 1
   --out q8-ref.jsonl`, then the same with `--kv q8_0`, no `--nmax` and `--out q8.jsonl`.
7. **The output check.** The clauses that differ at 8 bits for gemma-4-12B, Qwen3.5-9B,
   Qwen3.5-2B and gemma-4-26B-A4B in the checks of 2026-11-20 are still to be read against the
   prompt: `python3 q8-output-report.py --texts`. Qwen3.6-35B-A3B and the NVFP4 file of
   gemma-4-31B have no check, since no row holds them whole, and the CPU files have none on a
   CPU, since `q8-output.py` launches on the card.

Afterwards `python3 q8-report.py` rebuilds `q8.md`.

What would close it: Flash-Next's rows, the rule applied to it in the readings, and the result
recorded in ADR-0077 decision 8. A tier whose shipped file then meets the rule gets `q8_0` as the
default of its setting in `brain/packages/model_manager/src/cortex_model_manager/config.py`.
Steps 2 to 7 refine cells that are already decided.

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
- 2026-11-20: every row the list named was drawn except Qwen3.8-Flash-Next, each beside a 16-bit
  pair of the night: the NVFP4 file of gemma-4-31B split, Qwen3.8-27B at 64K, both MoE files,
  Qwen3.5-2B at 256K, the chat models' drafter cache and the CPU servers. No tier other than the
  deep tier meets the rule. The body was rewritten around the readings, with what is left. No
  default changed. Filed: R-1261 for the driver's allowance search, R-1262 for its cap on the CPU
  filled pass, R-1263 for the drafter's cache of a Qwen tier.
- 2026-11-20: the deep tier's default became `q8_0`, in `config.py` and as the compose default,
  on the draw of [R-1260](1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md),
  which closed. The cortex's and the subagent servers' defaults stay `f16`. Live check on build
  b12375: started on compose defaults with the pick's file and its drafter named, the deep
  tier's argv has `q8_0` for the model's cache and the drafter's, a request reached its reply,
  and the engine's log at level 4 names `K (q8_0)` and `V (q8_0)`
  ([readings](../../readings/kv-cache-deep-whole.md)). Filed:
  [R-1264](1264-the-deep-tier-at-16k-is-over-the-model-budget-with-every-layer-on-the-card.md)
  for the deep tier's fit at 16K.
