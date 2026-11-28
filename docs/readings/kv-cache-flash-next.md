# Readings: an 8-bit KV cache on Qwen3.8-Flash-Next

The rows of 2026-11-21 for
[R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md):
`Qwen3.8-Flash-Next-UD-Q4_K_XL` at `--cache-type-k q8_0 --cache-type-v q8_0`, each row beside a
16-bit row of the same night. It was the last model of the baseline of 2026-11-16 without cache
type rows. The file is a deep candidate of [ADR-0004](../adr/ADR-0004-model-lineup.md) decision 8
and no tier's file. It holds 103.7 GiB of weights, more than the card and more than the 94 GB of
memory the containers' Linux host had, so a launch keeps a part on the card and reads the rest
from RAM and from the models mount.

The rule a file must meet, the budget and the rate are those of
[the first cache type readings](kv-cache-types.md), and
[the rows of 2026-11-19](kv-cache-every-model.md) say why a ratio divides two rows of one night.
The build is b12375 from the `cortex-model-host` image. Every ratio divides an 8-bit row of
2026-11-21 by the 16-bit row of the same launch of that date. Memory is in MiB.

## How the rows are drawn

One server at a time on the 24 GB card, started with `--parallel 1 --jinja --cache-ram 0 -fa on
--threads 16 --fit on --fit-target 5500`. A drafted row names the file's `mtp` drafter with
`--model-draft`, adds `--spec-type draft-mtp --spec-draft-n-max <length>` and raises the target
to 5900. With `--fit on` the engine chooses how much of the file the card holds: it adds weights
in steps until the next step would leave less than the target free. An 8-bit row adds the two
cache flags, and `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0` when it drafts.

- **Two cells.** 256K, the file's training context, with three short prompts only, which leave
  the context nearly empty. 32K with the filled pass of the first readings (a prompt of the
  context less 512 tokens, 256 tokens written, the median of three seeds) and a draft ladder.
- **One launch per row.** No row was drawn twice and no launch failed to start. The 16-bit side
  has no draft and draft lengths 1 and 2. The 8-bit ladder has lengths 1 to 4 and ends there by
  the stop rule.
- **Power.** Every row ran at a median power limit ratio of 0.89, the highest the card reads.
- **The fixed launch** of
  [R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md)
  was the first and the last launch of the run: the last reads 0.996 of the first.
- **The floor.** The desktop's apps held 4,559 to 4,713 MiB before a row. Every row leaves more
  than 1,536 MiB free at its highest reading, with other apps counted as 4,750 MiB.

Method, under `measurements/model-baseline-2026-11-16/`, which git ignores: `python3
q8-probes/flash21.py f16`, then `python3 q8-probes/flash21.py q8_0`, then `python3
q8-probes/flash21.py row f16 2` for the 16-bit row at the fastest 8-bit length. The 16-bit rows
are in `bench/q8-ref.jsonl` and the 8-bit rows in `bench/q8.jsonl`, with `model`
`Qwen3.8-Flash-Next` and `time` `2026-11-21`. `python3 q8-probes/n21.py` prints them with every
ratio, and `q8-probes/notes-2026-11-21.md` has what the rows decide, written before them.

## What was written before the rows

A null result: every 8-bit rate inside 0.90 to 1.10 of its 16-bit row, and under 250 MiB of
difference in what the card holds. For condition 2 the reading expected was a fall under 250
MiB, because the fit fills the card toward the same target at both types.

## The rows

| cell | draft length | rate, 8-bit over 16-bit | prompt pass | short prompts | loaded at ready, 16-bit and 8-bit | 8-bit less 16-bit |
| --- | --- | --- | --- | --- | --- | --- |
| 256K, short prompts | none | not drawn | not drawn | 1.025 | 17,852 and 17,580 MiB | 272 MiB less |
| 32K, filled | none | 0.939 | 0.975 | 0.970 | 17,566 and 17,721 MiB | 155 MiB more |
| 32K, filled | 1 | 0.928 | 1.002 | 1.004 | 17,152 and 17,586 MiB | 434 MiB more |
| 32K, filled | 2 | 0.981 | 0.995 | 0.967 | 17,268 and 16,844 MiB | 424 MiB less |
| 32K, filled | 3 | no 16-bit row | | | 16,946 MiB at 8 bits | |
| 32K, filled | 4 | no 16-bit row | | | 17,057 MiB at 8 bits | |

"Loaded at ready" is `memory.used` when the server first answers its health check, less what
the card held before the load.

- **The rate moves little.** On the filled context the 8-bit rate is 0.928 to 0.981 of the
  16-bit rate, under it at each of the three lengths and above the rule's 0.90 at each. The
  three seeds of a row differ by up to 0.19 of their median.
- **The ladders.** At 8 bits the fastest length is 2, at 1.161 of the 8-bit no-draft rate;
  lengths 1, 3 and 4 read 1.031, 1.048 and 1.026 of it. At 16 bits length 2 is the fastest of
  the three rows drawn, at 1.111 of the no-draft rate, and length 1 reads 1.043.
- **The memory difference changes sign.** The card holds less at 8 bits in two cells and more
  in two. The highest reading of a row less the floor before the load differs the same way: 280
  less, 296 more, 430 more and 435 less.
- **The floor moved under two 8-bit rows**: up by 146 MiB under the no-draft row at 32K and down
  by 138 MiB under the row at draft length 2. With the floor read after the row those two
  differences are 153 more and 308 less.

## Where the fit puts the file

Each launch of draft lengths 0 and 1 was started once more with `-lv 4` and removed when the fit
had logged its placement, before any weights load (`python3 q8-probes/flashfit.py`, text in
`bench/flash-logs-2026-11-21/`). At every start the engine reads 23,119 MiB free of 24,435, puts
all 49 layers on the card and lets most of them overflow into RAM, as it does for the two
smaller MoE files. The three memory columns are the engine's own breakdown of the placement it
ends on.

| context | draft length | cache | layers overflowing | weights on the card | context on the card | compute | the fit's total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 256K | none | 16-bit | 47 | 8,704 | 7,792 | 1,050 | 17,548 |
| 256K | none | 8-bit | 45 | 11,954 | 4,198 | 1,118 | 17,271 |
| 32K | none | 16-bit | 43 | 15,204 | 1,072 | 994 | 17,272 |
| 32K | none | 8-bit | 42 | 15,796 | 628 | 994 | 17,420 |
| 32K | 1 | 16-bit | 45 | 11,046 | 1,185 | 994 | 16,789 |
| 32K | 1 | 8-bit | 45 | 11,498 | 741 | 1,402 | 17,202 |
| 32K | 2 | 16-bit | 45 | 11,046 | 1,297 | 994 | 16,901 |
| 32K | 2 | 8-bit | 45 | 11,046 | 853 | 994 | 16,455 |
| 32K | 3 | 16-bit | 45 | 11,046 | 1,410 | 994 | 17,014 |
| 32K | 3 | 8-bit | 45 | 11,046 | 966 | 994 | 16,568 |
| 32K | 4 | 16-bit | 45 | 11,046 | 1,522 | 994 | 17,126 |
| 32K | 4 | 8-bit | 45 | 11,046 | 1,079 | 994 | 16,680 |

In the drafted rows the three columns are the model's own, and the total includes the drafter,
about 3,560 MiB at both types. The rows at lengths 2 to 4 are from **2026-11-28**, with the
file read from the models mount, never copied: the six starts of 2026-11-21 were made again
that night and ended on the same totals to the MiB (`flashfit.py` with `DAY` set to the date,
text in `bench/flash-logs-2026-11-28/`).

- **The fit explains the 8-bit launches at lengths 2 to 4.** The rule written first: explained
  if each 8-bit total at lengths 2 to 4 is at least 400 MiB under the 8-bit total at length 1.
  They are 747, 634 and 522 MiB under it, where the rate rows loaded 742, 640 and 529 MiB less.
  At length 1 the fit's last accepted step moves part of one more layer onto the card, 452 MiB
  of weights and 408 MiB of compute, and ends 17 MiB inside its target. Each length above 1 adds
  112 MiB to the context the fit counts, which puts that step over the target (17,314 MiB at
  length 2), so the fit ends on the step below it, as at every drafted length at 16 bits.

- **The smaller cache moves weights onto the card.** At 256K the context is 3,594 MiB smaller
  and 3,250 MiB more of the weights are on the card, with two fewer layers overflowing. At 32K
  the context is 444 MiB smaller, and 592 MiB more weights are on the card without the drafter
  and 452 MiB more with it.
- **The fit's totals are the differences the rows read.** They differ by 277 less, 148 more and
  413 more at 8 bits, against 272 less, 155 more and 434 more loaded at ready. So what the card
  holds is set by the step the fit ends on, and so is the sign of the difference.
- **The 8-bit context is 0.539 of the 16-bit one at 256K and 0.586 at 32K**, not a half. The
  8-bit log below has a recurrent state of 113 MiB at 32-bit floats beside the caches. The four
  context sizes are what the caches take at each type and context plus that same state; no
  16-bit log was read to confirm it there.

## The cache lines the engine logs

This build names the cache type only at `-lv 4` and only after the weights load, so a rate row
has no such line. One 8-bit start at 32K without the drafter loaded the whole file at `-lv 4` and
was removed once it answered its health check (`bash q8-probes/chain48.sh q8_0`, row in
`bench/q8-kvlog.jsonl`):

```
llama_context: flash_attn            = enabled
llama_kv_cache: size =  408.00 MiB ( 32768 cells,  12 layers,  1/1 seqs), K (q8_0):  204.00 MiB, V (q8_0):  204.00 MiB
llama_memory_recurrent: size =  112.57 MiB (     1 cells,  48 layers,  1 seqs  0 rs_seq), R (f32):    4.22 MiB, S (f32):  108.00 MiB, P (f32):    0.35 MiB
llama_kv_cache: size =  102.00 MiB ( 32768 cells,  12 layers,  1/1 seqs), K (q8_0):  102.00 MiB, V (q8_0):    0.00 MiB
```

The second cache is the file's indexer cache, which holds keys only. The two caches, the
recurrent state and two rotation buffers of about 3 MiB each sum to the 628 MiB the fit counts as
context. The start ended on the fit's placement of the table above (42 layers overflowing,
17,420 MiB) and loaded 17,712 MiB, where the rate row loaded 17,721.

## Whether the reply changes

The check of the first readings, one prompt of 4,027 tokens at temperature 0. Its request went
once to each no-draft server before the server was removed, so the two 16-bit launches here are
the launch at 32K and the launch at 256K, which the fit places differently.

| pair | identical leading tokens | same token at the same place | tokens written |
| --- | --- | --- | --- |
| 16-bit at 32K and 16-bit at 256K | 103 | 111 | 114 and 114 |
| 16-bit and 8-bit at 32K, the pair the check compares | 21 | 35 | 114 and 114 |
| 16-bit and 8-bit at 256K | 21 | 22 | 114 and 119 |

Every reply ends on its own (`finish_reason` is `stop`), none is empty and none repeats itself.
The 8-bit reply at 32K names the same two records in the same order as the 16-bit reply and
words three clauses differently; the measurement notes read each of them against the prompt and
found what it names there. For this file two 16-bit launches already differ after 103 tokens,
so a part of the difference between the types is the placement's and not the cache's.

## The rule applied

1. **Accepted: yes.** All six 8-bit rate launches start with `-fa on` and answer, and the start
   at `-lv 4` names `K (q8_0)` and `V (q8_0)` for the model's cache. The drafter's cache lines
   were not read: that start has no drafter.
2. **Gain: yes as the condition is written, on differences the fit makes.** No step of context
   can be gained, since the file runs at its training context at both types. On memory the card
   holds 272 MiB less at 256K and 424 MiB less at 32K at draft length 2, the best length, and
   the condition asks for 250. Without drafting and at draft length 1 it holds 155 and 434 MiB
   more. The fit uses what the cache frees for weights, so each figure is what the fit's last
   step leaves over and not memory the cache returns. The fall expected before the rows was
   under 250 MiB; at 256K it reads 22 MiB over that.
3. **Rate: yes.** At 32K 0.939 without drafting and 0.981 at draft length 2, the best 8-bit
   length, with the prompt pass at 0.975 and 0.995; 0.928 at draft length 1. At 256K only short
   prompts were drawn, at 1.025.
4. **Output: does not fail.** The 8-bit reply at 32K states what the 16-bit reply states.

**Result: the file meets the rule as it is written.** Read against what was written first, the
rates are the null result. More weights on the card at 8 bits did not make this file faster, and
the smaller cache did not make it slower by a tenth. That differs from the dense files split
with RAM, which write 1.5 to 4.3 times their 16-bit rate at 8 bits, and from the two smaller
MoE files, which write 0.69 to 0.87 of it on a filled context
([2026-11-19](kv-cache-every-model.md), [2026-11-20](kv-cache-remaining-cells.md)). The file is
no tier's pick, so no default follows from these rows (ADR-0077 decision 8).

## What was not drawn

- 16-bit rows at draft lengths 3 and 4, so those two 8-bit rows have no ratio.
- A filled pass at 256K, a second launch of any row, the drafter's cache lines and a 16-bit
  start at `-lv 4`.

The first is in
[R-1270](../refinements/tasks/1270-some-cache-type-cells-have-no-row-beside-a-16-bit-row-of-their-own-night.md)
with its commands.
