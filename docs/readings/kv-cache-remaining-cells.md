# Readings: an 8-bit KV cache on the cells the first two nights left

The rows of 2026-11-20 for
[R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md):
the split files, the 256K cells, the drafter's cache for the chat models and the CPU servers,
each 8-bit row (`q8_0`) beside a 16-bit row of the same night. The rule a tier must meet, the
budget, the rate and the draft ladder are those of
[the first cache type readings](kv-cache-types.md), and [the rows of 2026-11-19](kv-cache-every-model.md)
say why a ratio divides two rows of one night. Card rows ran on build b12375 from the
`cortex-model-host` image, CPU rows on b10680 from the engine's CPU image. Memory is the highest
reading of a row less what the card held before the load, in MiB. Every ratio divides two rows
of 2026-11-20. [The deep tier as the model host starts it](kv-cache-deep-whole.md) has its own
record.

Method, under `measurements/model-baseline-2026-11-16/`, which git ignores: 16-bit rows are in
`bench/q8-ref.jsonl` and 8-bit rows in `bench/q8.jsonl`, both with `time` set to the date;
`python3 tools/q8-report.py` rebuilds `q8.md` with every absolute rate, and
`q8-probes/notes-2026-11-20.md` has what each group decides, written before its rows.

## One launch drawn eight times across the night

gemma-4-12B at 64K, 16 bits, no draft (`python3 q8-probes/drift.py`), drawn at the start and end
of each measurement session. The slowest row reads 0.966 of the fastest, and 0.980 without that
one row. So a ratio of this night can be off by about 0.02 to 0.03 from this cause.
[R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md)
has these rows beside the three of 2026-11-19.

## gemma-4-31B, the NVFP4 file, split with RAM

`--fit on`, 8 threads. The fit keeps more layers on the card at 8 bits:

| context | layers on the card, 16-bit and 8-bit | with the drafter | rate without drafting, 8-bit over 16-bit | at draft length 1 | prompt pass |
| --- | --- | --- | --- | --- | --- |
| 16K | 53 and 56 | 51 and 54 | 1.52, and 1.56 on a second pair of launches | 1.54 | 1.29 and 1.26 |
| 32K | 49 and 53 | 47 and 50 | 1.94 | 2.10 | 1.29 and 1.25 |

The Q4 file read 2.08 to 2.11 at both contexts on 2026-11-19, so this file gains less at 16K
and about as much at 32K. The 1.52 was under the 1.7 written first, so the pair was drawn once
more with the pass mark written before it (inside 0.9 to 1.1 of 1.52, the same layers): it held.
Card memory does not fall: the highest reading without drafting is 17,879 and 17,766 MiB at 16K
and 17,713 MiB at both types at 32K. The 8-bit ladder stops at draft length 5 at 16K with 3 the
fastest, and at 4 at 32K with 2 the fastest; the 16-bit pair has length 1 only.

Method: `python3 bench3.py --models gemma-4-31B-NVFP4 --kind moe --ctx 16384 --phase deep --nmax
1 --out q8-ref.jsonl`, then the same with `--kv q8_0 --out q8.jsonl` and no `--nmax`;
`q8-probes/rep.py` for the second pair.

## Qwen3.8-27B, the Q4 file, at 64K

At 16 bits the file is not held whole at 64K, so the fit leaves layers in RAM. At 8 bits it is
whole without its drafter and split with it.

| draft length | 16-bit placement | 8-bit placement | rate, 8-bit over 16-bit | prompt pass |
| --- | --- | --- | --- | --- |
| none | 57 layers, 17,537 MiB at load | every layer, 17,820 and 17,813 MiB at load | 4.25, and 4.32 on a second pair of launches | 1.39 and 1.37 |
| 1 | 55 layers | 61 layers | 2.71 | 1.25 |

- **The gain of a split file is not gemma-4-31B's alone.** A second dense file gains when the
  smaller cache lets more of it stay on the card.
- **4.25 and 4.32 are upper readings.** The driver's search for the fit's allowance did not end
  on a placement that fits for this cell, so every allowance was given by hand, and the 16-bit
  no-draft row has one step of the fit (about 456 MiB) less on the card than the largest
  placement that fits at load.
- **At 8 bits drafting is slower than not drafting here.** Lengths 1 to 5 read 0.68, 0.80, 0.81,
  0.71 and 0.69 of the 8-bit no-draft rate, because the drafted launch is split. The ladder stops
  at 5, and lengths 4 and 5 are over the budget at their highest reading (1,261 and 1,385 MiB
  free of the 1,536 needed), read while the floor moved by up to 288 MiB.

Method: `q8-probes/rep.py Qwen3.8-27B 65536 f16` with `REP_ALLOWANCE=586`, then `q8_0`;
`q8-probes/splitrow.py Qwen3.8-27B 65536 f16 row 1 600 <note>` and `bash q8-probes/chain42.sh
ladder8 500` for the drafted rows.

## The two MoE files

**Qwen3.6-35B-A3B at 256K, split with RAM.** The fit keeps 41 layers with 11 overflowing at 16
bits and 41 with 6 at 8 bits (42 with 15 and 42 with 10 with the drafter).

| draft length | rate, 8-bit over 16-bit | 8-bit rate over the 8-bit no-draft row of its run |
| --- | --- | --- |
| none | 0.73, and 0.74 on a second launch | |
| 1 | no 16-bit row | 0.94 |
| 2 | 0.83 | 1.25 |
| 4, 5, 6 | no 16-bit row | 1.22, 1.18, 1.07 |

Lengths 4, 5 and 6 fall, so the stop rule ends the 8-bit ladder at 6. Length 1 is slower than no
draft and length 2 faster, as on 2026-11-19 (0.93 and 1.27). Length 3, the fastest that night,
has no row of this night. The highest reading falls by 157 MiB without drafting.

**gemma-4-26B-A4B at 32K and 64K.** The fit changes nothing at either type, with or without the
drafter: the file is held whole at these contexts.

| context | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass |
| --- | --- | --- | --- | --- | --- |
| 32K | none | 15,035 MiB | 14,657 MiB | 0.829 | 0.99 |
| 32K | 1 | 15,559 MiB | 15,293 MiB | 0.848 | 0.97 |
| 64K | none | 15,707 MiB | 15,163 MiB | 0.720 | 0.98 |
| 64K | 1 | 16,263 MiB | 15,949 MiB | 0.757 | 0.96 |

So its loss at 256K (0.69 on 2026-11-19) does not come with the split: the file loses rate at 8
bits when it is whole on the card, and more at the larger context. Both 8-bit ladders stop at
draft length 4 with 2 the fastest, a length the 16-bit pair does not have.

Method: the NVFP4 commands above with `--models Qwen3.6-35B-A3B` and no `--ctx` (`--nmax 2` for
the 16-bit pair, `--nmax 4,5,6` and `--nmax 1,2` at 8 bits), and with `--models gemma-4-26B-A4B`
and `--ctx 32768` or `--ctx 65536`.

## Qwen3.5-2B at 256K

| draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass |
| --- | --- | --- | --- | --- |
| none | 4,959 MiB | 4,011 MiB | 0.917 | 0.95 |
| 2 | 5,861 MiB | 5,197 MiB | 0.813 | 0.95 |

Length 2 was the fastest of the 8-bit ladder on 2026-11-19. At both types drafting is slower
than no draft at this context. Method: `python3 q8-probes/ref.py Qwen3.5-2B 262144 subagent 0`,
then the two rows at 8 bits through `q8-probes/cellrow.py`.

## The chat models: the model's cache and the drafter's cache

With room kept for one subagent server. Each cell has a 16-bit pair, a ladder with the model's
cache at `q8_0` and the drafter's at `f16` (`--kv q8_0 --kv-draft f16`), and one row with both
at `q8_0`, at the draft length named.

| model | context | draft length | model cache 8-bit over 16-bit, no draft | at the draft length, both caches 8-bit | drafter cache 16-bit over 8-bit | memory at load, drafter cache 16-bit less 8-bit |
| --- | --- | --- | --- | --- | --- | --- |
| gemma-4-12B | 64K | 2 | 0.855 | 0.829 | 0.998 | none |
| gemma-4-12B | 128K | 3 | 0.745 | 0.793 | 0.985 | none |
| Qwen3.5-9B | 64K | 3 | 0.961 | 0.885 | 1.004 | 150 MiB less |
| Qwen3.5-9B | 128K | 3 | 0.955 | 0.775 | 0.955, and 1.036 on a second pair | 286 MiB less, and 292 |

- **The model's cache at 8 bits loses rate in every cell**, and more at the larger context.
  The no-draft row of gemma-4-12B at 64K is divided by the fixed launch above; over its eight
  rows the ratio is 0.84 to 0.87. Qwen3.5-9B at 64K and draft length 3 read 0.91 on 2026-11-19
  and reads 0.885 here, on either side of the rule's 0.90.
- **The drafter's cache type moves nothing for gemma-4-12B**: the same memory to 8 MiB and the
  same rate.
- **For Qwen3.5-9B the drafter's cache at 16 bits takes less memory**, 150 MiB at 64K and 286
  MiB at 128K at load (148 and 272 MiB at the highest reading), at the same rate. The 128K pair
  was drawn again with the pass mark written first (246 to 326 MiB, a ratio inside 0.90 to
  1.05): it held, at 292 MiB. The rows do not show why the 8-bit drafter cache is the larger
  one.
- The ladders with the drafter's cache at 16 bits are fastest at draft length 3 at 64K for both
  models and at 4 at 128K.

Method: per cell `bash q8-probes/chain31.sh <tag> <model> <context> <16-bit lengths> <length>`,
which draws each row on a fresh launch through `q8-probes/cellrow.py`.

## The CPU subagent servers

Four threads, thinking off, a container of 4 CPUs and 8 GB, no card memory involved. "Memory" is
the container's.

**8K, the context the CPU servers ship with.** gemma-4-E4B with flash attention off, its
model card's setting, does not start at 8 bits: `quantized V cache requires flash_attn to be
enabled`. With it on:

| model | rate without drafting, 8-bit over 16-bit | at one draft length | prompt pass, no draft | memory, no draft |
| --- | --- | --- | --- | --- |
| gemma-4-E4B, flash attention on | 1.054 | 1.26 at length 3 | 0.71 | about 76 MiB less |
| Qwen3.5-2B | 1.007 | 1.050 at length 1 | 0.75 | 46 MiB less |
| Qwen3.5-0.8B | 1.000 | 1.003 at length 1 | 0.62 | 39 MiB less |

Flash attention on reads 0.83 of the rate with it off for gemma-4-E4B at 16 bits without
drafting. So 8 bits with the flag on, over what the server ships with (16 bits, flag off), is
0.875 on a filled context and 0.70 on the prompt pass.

**16K and 32K, no draft only.**

| model | context | rate, 8-bit over 16-bit | prompt pass | memory |
| --- | --- | --- | --- | --- |
| Qwen3.5-2B | 16K | 1.072 | 0.627 | about 88 MiB less |
| Qwen3.5-0.8B | 16K | 1.120 | 0.476 | 90 MiB less |
| Qwen3.5-0.8B | 32K | 1.242 | 0.237 | 175 MiB less |

The written rate rises with the context and the prompt pass falls much further. gemma-4-E4B at
16K and 32K and Qwen3.5-2B at 32K have short prompts only, at 0.98 to 1.01 of the 16-bit rate,
because the driver's cap on a slow prompt pass draws no filled pass there.

Method: `python3 bench3.py --models gemma-4-E4B,Qwen3.5-2B,Qwen3.5-0.8B --kind cpu --phase cpu
--ctx 8192 --out q8-ref.jsonl` and the same with `--kv q8_0 --out q8.jsonl`, with `--fa on` for
gemma-4-E4B; `python3 q8-probes/cpurow.py <model> <context> f16|q8_0 [on|off]` for one no-draft
row.

## Whether the reply changes

The check of the first readings: one prompt of about 4,000 tokens at temperature 0 at 8K, every
layer on the card, twice at 16 bits and once at 8 bits.

| model | tokens written, 16-bit and 8-bit | identical leading tokens, two 16-bit launches | identical leading tokens, 16-bit and 8-bit |
| --- | --- | --- | --- |
| gemma-4-31B, Q4 file, held whole | 119 and 119 | 119 | 119 |
| gemma-4-26B-A4B | 95 and 105 | 95 | 17 |
| gemma-4-12B | 119 and 119 | 119 | 5 |
| Qwen3.5-9B | 162 and 161 | 162 | 154 |
| Qwen3.5-2B | 62 and 64 | 62 | 33 |

Every reply ends on its own, none is empty and none repeats itself. gemma-4-31B's 8-bit reply is
its 16-bit reply. The 8-bit reply of gemma-4-26B-A4B words three clauses differently; the
measurement notes found each thing it names in the prompt by a word search, and one link (gRPC
"to ensure statelessness and portability") is the reply's own. The clauses that differ for the
other three were not read against the prompt this night; the same checks passed on 2026-11-18
and 2026-11-19. Qwen3.6-35B-A3B and the NVFP4 file of gemma-4-31B have no check, since no row
holds them whole. Method: `python3 tools/q8-output.py <model>`, read with `python3
tools/q8-output-report.py --texts`.

## The rule applied to these rows

| tier | model and file | 1 accepted | 2 gain | 3 rate | 4 output | result |
| --- | --- | --- | --- | --- | --- | --- |
| deep | gemma-4-31B, NVFP4 file, split | yes | no fall in card memory; 3 to 4 more layers on the card | yes: 1.52 to 2.10 | not drawn | not decided |
| deep | Qwen3.8-27B, Q4 file, at 64K | yes | whole at 64K without the drafter, where 16 bits is split | yes: 4.25 and 2.71 | passed 2026-11-18 | meets it, as on the rows held whole |
| deep | Qwen3.6-35B-A3B, split | yes | no: 157 MiB | no: 0.73 and 0.83 | not drawn | does not meet it |
| deep | gemma-4-26B-A4B, whole at 32K and 64K | yes | yes: 266 to 544 MiB | no: 0.72 to 0.85 | does not fail | does not meet it |
| chat | gemma-4-12B | yes | recorded on 2026-11-18 | no: 0.855 and 0.829 at 64K, 0.745 at 128K | passes | does not meet it |
| chat | Qwen3.5-9B | yes | recorded on 2026-11-18 | no: 0.885 at 64K and draft length 3, 0.775 at 128K | passes | does not meet it |
| subagent | Qwen3.5-2B at 256K | yes | yes: 948 MiB | no: 0.813 at draft length 2 | passes | does not meet it |
| CPU subagent | gemma-4-E4B | no with the card's setting; yes with flash attention on | no card memory | no: prompt pass 0.71 | not drawn on a CPU | does not meet it |
| CPU subagent | Qwen3.5-2B, Qwen3.5-0.8B | yes | no card memory | no: prompt pass 0.75 and 0.62 at 8K, 0.24 to 0.63 above | not drawn on a CPU | do not meet it |

- **No tier other than the deep tier meets the rule on a night's own rows.** The chat tier, the
  GPU subagent files and the CPU servers lose rate or prompt pass, and the two MoE files lose
  rate whole and split.
- **The split files gain rate and no card memory.** Condition 2 was written for a model held
  whole, and the stack does not start a tier split, so the NVFP4 file of gemma-4-31B is not
  decided by these rows.
- **The drafter's cache.** Left at 16 bits it saves 286 to 292 MiB for Qwen3.5-9B at 128K and
  nothing for gemma-4-12B. The host gives the drafter the model's type; no tier ships at `q8_0`
  with a Qwen draft layer, so nothing changes on these rows.

No default changed on these rows. R-1243 has the cells that are left: Qwen3.8-Flash-Next, one
draft length of Qwen3.6-35B-A3B, the drafted CPU rows, and the 16-bit rows at the fastest 8-bit
lengths. It also names the tasks filed for the driver's allowance search, its cap on the CPU
filled pass and the drafter's cache of a Qwen tier.
