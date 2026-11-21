# Readings: an 8-bit KV cache on every model, each ratio inside one night

The rows of 2026-11-19 for
[R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md):
every model [the baseline of 2026-11-16](model-baseline.md) drew that has rows at
`--cache-type-k q8_0 --cache-type-v q8_0`, set beside a 16-bit row of the same night. The rule a tier must meet, the budget, the rate
and the draft ladder are those of [the first cache type readings](kv-cache-types.md), on the same
build, b12375 from the `cortex-model-host` image. Memory is the highest reading of a row less what
the card held before the load, in MiB. A rate is a ratio, and each ratio says which two rows it
divides.

## Why a ratio is formed inside one night

**2026-11-19.** The same 16-bit launch reads a higher rate on this night than on the night the
baseline drew it. For one cell per model the 16-bit launch was drawn again, without drafting and
at the fastest draft length of the cell's 8-bit ladder. The night factor is that row's rate over
the earlier row's:

| model | cell | earlier row drawn | night factor, no draft | night factor, drafting | 8-bit over 16-bit of the same night | 8-bit over the earlier 16-bit |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8-27B, Q4 file | 20K | 2026-11-17 | 1.14 | 1.12 | 0.92 and 0.92 | 1.05 and 1.03 |
| Qwen3.8-27B, NVFP4 file | 20K | 2026-11-18 | 1.08 | 1.09 | 0.93 and 0.93 | 1.00 and 1.01 |
| gemma-4-12B | 64K | 2026-11-16 | 1.15 | 1.16 | 0.85 and 0.88 | 0.97 and 1.02 |
| Qwen3.5-9B | 64K | 2026-11-17 | 1.06 | 1.08 | 0.95 and 0.91 | 1.01 and 0.98 |
| gemma-4-E2B | 16K | 2026-11-16 | 1.23 | 1.21 | 0.83 and 0.89 | 1.02 and 1.08 |
| Qwen3.5-4B | 16K | 2026-11-17 | 1.09 | 1.09 | 1.00 and 1.01 | 1.09 and 1.11 |
| Qwen3.5-2B | 16K | 2026-11-17 | 1.15 | 1.10 | 1.00 and 0.99 | 1.14 and 1.08 |
| Qwen3.5-0.8B | 16K | 2026-11-17 | 1.14 | 1.14 | 0.98 and 1.11 | 1.12 and 1.27 |

- **One launch drawn three times did not move inside the night.** The 16-bit launch of
  gemma-4-12B at 64K without drafting was drawn as the first and the last row of one slot and
  once in the slot before. The two slower rows read 0.975 and 0.98 of the fastest. The four
  gemma-4-31B launches below that have a second row read 0.985 to 0.996 of their faster row.
- **The rows do not record a cause.** Every row of 2026-11-19 ran at a median power limit ratio
  of 0.89, the highest the card reads. The earlier rows record the lowest reading, 0.80 to 0.89,
  and four of them a median, 0.89 for three and 0.85 for one. The highest temperature, the draw
  while busy and the clock ratio of the two nights agree
  ([R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md)).
- **So a ratio across two nights is wrong by the factor of its model**, and for five of the
  eight models that is more than the 0.10 the rule's rate condition allows. Every ratio below
  divides two rows of 2026-11-19 unless it says otherwise. "Divided by the night factor" is
  the ratio over an earlier 16-bit row divided by the factor in the table above, which was read
  at one context per model. Memory does not depend on the night.
- **8-bit rows of two nights differ the same way.** The six 8-bit launches drawn without drafting
  on both nights read 1.05 to 1.11 times their rows of 2026-11-18: Qwen3.8-27B at 48K and 64K,
  its NVFP4 file at 48K and 80K, and Qwen3.5-4B and Qwen3.5-2B at 8K.

Method, under `measurements/model-baseline-2026-11-16/`, which git ignores: `q8-probes/ref.py
<model> <context> <phase> <room kept>` draws the 16-bit pair of a cell into `bench/q8-ref.jsonl`,
`python3 tools/q8-report.py --night` prints the table, and `q8-probes/drift.py` draws the repeated
launch. The 8-bit rows are in `bench/q8.jsonl`, and `q8.md` has every row with its absolute rate
and the date of both sides of each ratio.

## The deep tier, held whole: Qwen3.8-27B

Both files at 20K, each beside its 16-bit pair of the night:

| file | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- | --- | --- |
| Q4 | none | 16,686 MiB | 16,116 MiB | 0.92 | 1.02 |
| Q4 | 4 | 17,908 MiB | 17,335 MiB | 0.92 | 0.96 |
| NVFP4 | none | 16,437 MiB | 15,816 MiB | 0.93 | 0.94 |
| NVFP4 | 2 | 17,450 MiB | 16,826 MiB | 0.93 | 0.98 |

Draft length 4 is the fastest of the Q4 file's 8-bit ladder at 20K and 2 of the NVFP4 file's. The
other lengths at 20K and the ladders at 16K and 24K have no 16-bit row of the night. Divided by
the night factor they read 0.84 to 0.92 for the Q4 file at 20K and 0.86 to 1.00 for the NVFP4
file at 16K, 20K and 24K. Memory falls by 557 to 568 MiB for the Q4 file at 20K, where draft
length 6 fits at 8 bits and is over the budget at 16, and by 474 to 714 MiB for the NVFP4 file.
The search gives the largest contexts of 2026-11-18 again: 48K with the draft layer and 64K
without for the Q4 file, 48K and 80K for the NVFP4 file.

**The drafter's cache at 16 bits beside an 8-bit model cache** (`--kv q8_0 --kv-draft f16`), both
files at 48K: the server takes 82 to 86 MiB less at load at draft lengths 1 to 3, under the 250
MiB of the rule. The search ends on 48K again for both files. The rate is 0.99 to 1.01 of the row
with both caches at 8 bits, which is a row of 2026-11-18 and is divided by the night's ratio of
the no-draft rows at 48K (1.06 and 1.08). One cell moves inside the budget: the NVFP4 file at
draft length 3 fits by 14 MiB where it was 57 MiB over.

## The deep tier, split with RAM: gemma-4-31B, the Q4 file

At 16 bits the file fits whole at no context under the 18,177 MiB budget. At 8 bits it fits
whole at 12K without its drafter, at 18,173 MiB, and at no context with it. The NVFP4 file fits
whole at no context at either type.

Split with RAM (`--fit on`, 8 threads), the engine keeps more layers on the card at 8 bits,
because the context takes less of the budget:

| context | cache | layers on the card, without and with the drafter | weights on the card | context on the card | highest reading, no draft | RAM, no draft |
| --- | --- | --- | --- | --- | --- | --- |
| 16K | 16-bit | 55 and 53 | 14,900 MiB | 2,232 MiB | 17,705 MiB | 3.95 GiB |
| 16K | 8-bit | 59 and 56 | 15,957 MiB | 1,314 MiB | 17,841 MiB | 2.27 GiB |
| 32K | 16-bit | 51 and 49 | 13,872 MiB | 3,288 MiB | 17,882 MiB | 4.20 GiB |
| 32K | 8-bit | 56 and 53 | 15,186 MiB | 1,955 MiB | 17,865 MiB | 2.33 GiB |

| context | draft length | rate, 8-bit over 16-bit of the night | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- |
| 16K | none | 2.08, and 2.10 on a second pair of launches | 1.30 |
| 16K | 1 | 1.81 | 1.21 |
| 32K | none | 2.09, and 2.11 on a second pair of launches | 1.29 |
| 32K | 1 | 2.67 | 1.26 |

- **The result was drawn twice.** The second pair is four no-draft rows, each on a fresh launch,
  the 16-bit row first at 16K and the 8-bit row first at 32K. The pass mark was written before
  them: 1.7 at both contexts and the same layer counts. Both held.
- **Card memory does not fall**, since the fit uses what the cache frees for weights. RAM falls
  by 1.7 to 1.9 GiB.
- **Drafting.** The 8-bit ladders run to draft length 6 and every length fits. The fastest is 5 at
  16K, at 1.22 of the 8-bit no-draft rate, and 3 at 32K, at 1.34. The 16-bit pair has draft
  length 1 only, which is slower than no draft at 32K.
- **Held whole at 12K** the 8-bit row writes 1.54 times the 8-bit split row at 16K.

Method: `python3 bench3.py --models gemma-4-31B --kind moe --ctx 16384 --phase deep --kv q8_0
--out q8.jsonl` and the same with `--ctx 32768`; the 16-bit pairs with `--out q8-ref.jsonl` and no
`--kv`; `q8-probes/rep.py` for the second pair.

## The two MoE models at 256K, split with RAM

Both keep every layer on the card and let some of them overflow into RAM. At 8 bits fewer
overflow, and the rate on a filled context falls all the same:

| model | cache | layers (overflowing), without and with the drafter | weights on the card, no drafter | highest reading, no draft | rate, 8-bit over 16-bit of the night |
| --- | --- | --- | --- | --- | --- |
| gemma-4-26B-A4B | 16-bit | 31 (6) and 31 (8) | 11,524 MiB | 17,875 MiB | |
| gemma-4-26B-A4B | 8-bit | 31 (2) and 31 (6) | 13,157 MiB | 17,751 MiB | 0.69 without drafting, 0.74 at draft length 1 |
| Qwen3.6-35B-A3B | 16-bit | 41 (11) and 42 (15) | 11,876 MiB | 17,942 MiB | |
| Qwen3.6-35B-A3B | 8-bit | 41 (6) and 42 (10) | 13,810 MiB | 17,786 MiB | 0.72 without drafting, 0.87 at draft length 2 |

Short prompts, which leave the context nearly empty, are faster at 8 bits: 1.39 and 1.10 times
for gemma-4-26B-A4B, 1.28 and 1.12 times for Qwen3.6-35B-A3B. The 8-bit ladder of
gemma-4-26B-A4B stops at draft length 3 with 1 the fastest, at 1.08 of its no-draft rate. That of
Qwen3.6-35B-A3B has lengths 1 to 4 and no stop yet: 3 is the fastest, at 1.36, and length 1 is
slower than no draft (0.93) where length 2 reads 1.27, a step the 16-bit ladder of the baseline
does not have.

## The chat tier at 64K

With room kept for one subagent server, each model beside its 16-bit pair of the night:

| model | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- | --- | --- |
| gemma-4-12B | none | 8,383 MiB | 7,776 MiB | 0.85 | 0.97 |
| gemma-4-12B | 2 | 8,946 MiB | 8,449 MiB | 0.88 | 0.98 |
| Qwen3.5-9B | none | 7,525 MiB | 6,757 MiB | 0.95 | 0.98 |
| Qwen3.5-9B | 3 | 8,398 MiB | 7,625 MiB | 0.91 | 0.97 |

The 8-bit ladders at 128K and 256K were drawn too and have no 16-bit row of the night; `q8.md`
has them beside the baseline's rows.

## The subagent tier

**gemma-4-E4B with flash attention on**, which is how the stack runs it. Each pair is of one
night: 2026-11-18 for the no-draft rows at 8K and 64K, 2026-11-19 for every other row.

| context | 16-bit memory, no draft | 8-bit memory, no draft | rate without drafting, 8-bit over 16-bit | fastest 8-bit length over fastest 16-bit length |
| --- | --- | --- | --- | --- |
| 4K | 3,011 MiB | 2,995 MiB | 0.91 | 0.96 |
| 8K | 3,072 MiB | 3,029 MiB | 0.93 | 0.97 |
| 16K | 3,215 MiB | 3,143 MiB | 0.87 | 0.96 |
| 32K | 3,487 MiB | 3,357 MiB | 0.81 | 0.87 |
| 64K | 4,041 MiB | 3,790 MiB | 0.67 | 0.78 |
| 128K | 5,123 MiB | 4,655 MiB | 0.58 | 0.62 |

With the drafter the memory changes by 26 MiB or less up to 32K, and at 64K and 128K it rises
by 8 to 48 MiB. At 8K the pairs of one night read 0.91 to 1.01 across the draft lengths.

**The four small models** each hold their training context with their drafter at both types
(128K for gemma-4-E2B, 256K for the three Qwen files), so no model gains a step of context.

| model | 16K, memory fall without and with drafting | 16K, rate of the night, without and with drafting | largest context, memory fall without drafting | largest context, rate without drafting, divided by the night factor |
| --- | --- | --- | --- | --- |
| gemma-4-E2B | none (14 MiB more, 3 MiB less) | 0.83 and 0.89 | 153 MiB | 0.60 |
| Qwen3.5-4B | 185 and 166 MiB | 1.00 and 1.01 | 2,825 MiB | 0.87 |
| Qwen3.5-2B | 78 and 62 MiB | 1.00 and 0.99 | 946 MiB | 0.88 to 0.92 |
| Qwen3.5-0.8B | 62 and 34 MiB | 0.98 and 1.11 | 971 MiB | 0.88 |

At 256K the fastest 8-bit draft length is 3 for Qwen3.5-4B, 2 for Qwen3.5-2B and 1 for
Qwen3.5-0.8B. Those 8-bit rows read 0.78, 0.87 and 0.89 of the earlier night's 16-bit row at the
same length before any division.

## Whether the reply changes

The check of the first readings, one prompt of about 4,000 tokens at temperature 0, for every
model that has rows. gemma-4-E4B ran with flash attention on at both types. gemma-4-31B ran split
with RAM at 16K at both types, since its 16-bit cache is held whole at no context.

| model | tokens written, 16-bit and 8-bit | identical leading tokens, two 16-bit launches | identical leading tokens, 16-bit and 8-bit |
| --- | --- | --- | --- |
| gemma-4-E4B | 109 and 97 | 109 | 0 |
| gemma-4-E2B | 84 and 80 | 84 | 37 |
| Qwen3.5-4B | 105 and 101 | 105 | 30 |
| Qwen3.5-2B | 62 and 64 | 62 | 33 |
| Qwen3.5-0.8B | 118 and 117 | 118 | 114 |
| Qwen3.8-27B, NVFP4 file | 112 and 117 | 112 | 4 |
| gemma-4-31B, split | 120 and 100 | 120 | 13 |

Two 16-bit launches write the same reply token for token for each model. Every reply ends on its
own, none is empty and none repeats itself, and each 8-bit reply states what its 16-bit reply
states in other words. No reply fails the check. gemma-4-12B, Qwen3.5-9B and the Q4 file of
Qwen3.8-27B passed it on 2026-11-18. Method: `python3 q8-output.py <model>`, `q8-probes/outfa.py`
and `q8-probes/outsplit.py`, read with `python3 q8-output-report.py --texts`.

## The rule applied

The four conditions are those of [the first readings](kv-cache-types.md).
Condition 3 is read on ratios of one night where a pair exists.

| tier | model and file | 1 accepted | 2 gain | 3 rate | 4 output | result |
| --- | --- | --- | --- | --- | --- | --- |
| deep | Qwen3.8-27B, Q4 file | yes | yes: 24K to 48K, and 570 MiB at 20K | yes: 0.92 and 0.92 at 20K the same night | passes | meets it, 0.02 above the mark |
| deep | Qwen3.8-27B, NVFP4 file | yes | yes: 32K to 48K, and 621 MiB at 20K | no: 0.93 at 20K, but 0.81 at 32K and draft length 1, both rows of 2026-11-18 | passes | does not meet it |
| deep | gemma-4-31B, Q4 file, split with RAM | yes | no step with the drafter and no fall in card memory; 4 to 5 more layers on the card | yes: 2.08 to 2.11 without drafting | passes | not decided |
| deep | gemma-4-26B-A4B and Qwen3.6-35B-A3B, split | yes | no: 124 and 156 MiB | no: 0.69 and 0.72 | not drawn | do not meet it |
| chat | gemma-4-12B | yes | yes: one step | no: 0.85 and 0.88 at 64K | passes | does not meet it |
| chat | Qwen3.5-9B | yes | yes: one step | 0.95 and 0.91 at 64K; no: 0.67 at 192K and draft length 3 across two nights | passes | does not meet it |
| subagent | gemma-4-E4B, flash attention on | yes | no: 16 to 130 MiB up to 32K | no: 0.87 at 16K, 0.58 at 128K | passes | does not meet it |
| subagent | gemma-4-E2B | yes | no | no: 0.83 at 16K | passes | does not meet it |
| subagent | Qwen3.5-4B, Qwen3.5-2B, Qwen3.5-0.8B | yes | no step; 34 to 185 MiB at 16K, 946 to 2,825 MiB at 256K | yes at 16K; no at 256K across two nights: 0.78, 0.87 and 0.89 at the fastest 8-bit length before any division | passes | do not meet it |

- **The Q4 file of Qwen3.8-27B still meets the rule.** Its ratios of 2026-11-18 at 16K and 24K
  were an 8-bit row over a 16-bit row of 2026-11-17 and read 0.97 to 1.00. The pair of one night
  at 20K reads 0.92, which passes the 0.90 of condition 3 by 0.02.
- **The NVFP4 file does not.** Its 0.81 at 32K is a ratio of two rows of 2026-11-18.
- **gemma-4-31B is not decided.** Condition 2 was written for a model held whole: it asks for a
  step of context with the drafter or 250 MiB less card memory, and split with RAM the file shows
  neither, because the fit uses the freed memory for layers on the card. That shape is where
  the rate doubles. The stack does not start the deep tier in that shape. The deep tier's
  `TierArgs` in `config.py` takes `ngl` from `CORTEX_NGL_BRAIN`, 99 by default, and
  `llama_server_argv` in `tiers.py` writes `-ngl` and no `--fit` flag, so the tier starts with
  every layer on the card, a shape in which this file has one 8-bit row (12K, no drafter) and no
  16-bit row. [The draw of 2026-11-20 in that shape](kv-cache-deep-whole.md) has both types,
  and the file meets the rule there
  ([R-1260](../refinements/tasks/1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md)).
- **The small Qwen files save memory only where they lose rate.** At the 8K to 16K a subagent
  server runs the fall is under 250 MiB. At 256K it is over, and no pair of one night exists
  there. Without drafting the rate divided by the night factor is under 0.90 for two of the three
  and 0.88 to 0.92 for Qwen3.5-2B. At the fastest 8-bit draft length all three are under 0.90
  before any division, and every factor read so far is above 1, so division lowers them.
- **Qwen3.5-9B passes at 64K and fails at 192K.** The 0.67 there divides rows of two nights, and
  no factor read so far is large enough to lift it to 0.90.

No default changed (ADR-0077 decision 8). [The rows of 2026-11-20](kv-cache-remaining-cells.md)
have the cells this night left: the CPU rows, the drafter's cache for the chat models, the split
files, Qwen3.5-2B at 256K beside a pair of its own night, and the last draft lengths of
Qwen3.6-35B-A3B. [The rows of 2026-11-21](kv-cache-flash-next.md) have Qwen3.8-Flash-Next.
