# Readings: the Q4 and NVFP4 deep files on one night

Rate and memory rows of 2026-11-22 for the two files each deep entry could name, its Q4 file and
its NVFP4 file, with both files of a pair drawn in turn on one night at a 16K context. The
maintainer asked for them so that the choice held in
[R-1244](../refinements/tasks/1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)
rests on rows of one night. This record says what was read and makes no choice.

[The NVFP4 files for the deep tier](nvfp4-deep-tier.md) has the four files' names and sizes, the
loader facts, the budget and the rows at other contexts, which divide two nights.
[What the Qwen NVFP4 file writes](nvfp4-deep-counts.md) has that file's stop, injection and
handoff counts. A rate describes only the card it was read on, so each one is written as a ratio
of another row of the same night. Memory is absolute: the highest `memory.used` of a row less
what the card held before the load.

## Qwen3.8-27B at 16K, held whole on the card

**2026-11-22**, build b12375, the two files in turn inside every group of launches. Every row has
a median power limit of 0.89 of the card's maximum and no reading under 0.87, and every row keeps
the 1,536 MiB free. One fixed launch (gemma-4-12B at 64K, the launch of
[R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md)),
drawn five times across the night, stayed within 0.985 to 1.003 of its first row, so no ratio
here is corrected for the night.

The model host started each cell as the stack starts the deep tier: alone on the card,
`--ctx-size 16384 --parallel 1`, the file's own draft layer at `--spec-draft-n-max 3` or no
drafter, and the cache type `q8_0`, the tier's default, or `f16`. The tier ships as the draft
layer at `q8_0`.

**Eight cells on three texts.** Two launches a cell, each the median of three texts (seeds 7 to
9) written after a prompt of 15,897 tokens. A cell is the mean of its two launches. Its rate and
prompt pass are over the Q4 `q8_0` cell with the same drafter setting.

| drafter | cell | rate | its two launches apart | prompt pass | highest reading above the floor |
| --- | --- | --- | --- | --- | --- |
| draft layer, length 3 | Q4 `q8_0` | 1 | 0.004 | 1 | 16,996 MiB |
| | Q4 `f16` | 1.096 | 0.009 | 1.008 | 17,470 MiB |
| | NVFP4 `q8_0` | 1.014 | 0.018 | 1.803 | 16,806 MiB |
| | NVFP4 `f16` | 1.010 | 0.000 | 1.781 | 17,296 MiB |
| none | Q4 `q8_0` | 1 | 0.016 | 1 | 15,958 MiB |
| | Q4 `f16` | 1.045 | 0.004 | 0.986 | 16,409 MiB |
| | NVFP4 `q8_0` | 1.023 | 0.040 | 1.837 | 15,676 MiB |
| | NVFP4 `f16` | 1.092 | 0.033 | 1.774 | 16,145 MiB |

At `q8_0` the NVFP4 file takes 190 MiB less than the Q4 file with the draft layer and 282 MiB
less without it; at `f16`, 174 and 264 MiB less. The 8-bit cache takes 452 to 490 MiB less than
the 16-bit one in every pair.

**Twelve texts correct the drafted rows.** A second launch replays the same three texts: it
drafts and accepts the same counts of tokens, so two launches that agree say nothing about other
texts, and the three texts of one drafted launch sit 9% to 16% apart. The four drafted cells
were drawn again on twelve texts (seeds 7 to 18), two launches a cell. A text's rate is the mean
of its two launches, and a cell's two launches sit 0.002 to 0.015 apart by the mean of the
twelve. The texts of a cell have a standard deviation of 0.052 to 0.074 of their mean. The two
Q4 `f16` launches came after the other six, not in turn with them; the fixed launch, drawn
before the first of the eight and again after the last, read 0.992 of its first row.

| draft layer at length 3 | mean of twelve texts | median | two standard errors | three texts |
| --- | --- | --- | --- | --- |
| NVFP4 `q8_0` over Q4 `q8_0`, the tier as it ships | 0.943 | 0.968 | 0.059 | 1.014 |
| NVFP4 `f16` over Q4 `q8_0` | 0.966 | 0.970 | 0.060 | 1.010 |
| NVFP4 `f16` over Q4 `f16` | 0.928 | 0.918 | 0.052 | 0.921 |
| Q4 `q8_0` over Q4 `f16` | 0.961 | 0.947 | 0.052 | 0.913 |
| NVFP4 `q8_0` over NVFP4 `f16` | 0.977 | 0.998 | 0.059 | 1.004 |

The twelve-text columns are the reading of the drafted cells, and the last column is what they
replace. As the tier ships, the NVFP4 file is not shown to write at another rate than the Q4
file: both readings are inside 1 plus or minus two standard errors, both are under 1, and the
1.014 of three texts is not seen again. With both files at `f16` the NVFP4 file is the slower
one by more than two standard errors. The cells without a drafter have three texts only: the
NVFP4 file reads 1.023 of the Q4 file at `q8_0` and 1.045 at `f16`, on launches up to 0.040
apart, and the 8-bit rate is 0.957 of the 16-bit rate for the Q4 file and 0.937 for the NVFP4
file.

**Draft ladders.** One launch a length for each file at each cache type, in turn, by the
baseline's driver (`-fa on`, the file read from RAM), three texts a launch. Each length over the
same ladder's no-draft row:

| ladder | 1 | 2 | 3 | 4 | 5 | 6 | fastest length, over length 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q4 `q8_0` | 1.23 | 1.54 | 1.71 | 1.62 | 1.72 | 1.65 | 5, 1.007 |
| Q4 `f16` | 1.25 | 1.48 | 1.78 | 1.71 | 1.80 | 1.73 | 5, 1.014 |
| NVFP4 `q8_0` | 1.36 | 1.67 | 1.60 | 1.61 | 1.53 | 1.38 | 2, 1.049 |
| NVFP4 `f16` | 1.43 | 1.60 | 1.60 | 1.63 | 1.46 | 1.33 | 4, 1.020 |

Every length fits, at about 150 MiB more a length. Three of the fastest lengths are within 1.02
of length 3, less than one launch of three texts separates. For the NVFP4 file at `q8_0`, length
2 over length 3 reads 1.049 here and, on three other texts (seeds 107 to 109), 1.049 by the
median and 1.039 by the mean, where the Q4 file reads 0.966 and 0.928. Over the six texts a
length that is 1.05 to 1.06 with a standard error of about 0.04: length 2 read faster twice and
is not shown to be faster. The ladders' no-draft launches read the NVFP4 file at 1.062 (`q8_0`)
and 1.066 (`f16`) of the Q4 file, one launch each.

Method, under `measurements/model-baseline-2026-11-16/`: `nvfp4-probes/pairwhole.py` for the
cells (`PAIR_SEEDS=12` for twelve texts), `nvfp4-probes/ladder2.py` for the ladders and the two
lengths, `q8-probes/drift.py` for the fixed launch. Rows: `bench/pair-whole-2026-11-22.jsonl`,
`pair-whole12-2026-11-22.jsonl`, `pair-ladder-2026-11-22.jsonl` and
`pair-lengths-2026-11-22.jsonl`. `nvfp4-probes/notes-2026-11-22.md` has what each group was to
decide, written before it, and the absolute rates.

## A deep reply in ratios

A handoff's deep reply takes the prompt pass over the handoff's prompt and then the writing.
The table below is computed from the Qwen rows above, with the draft layer at length 3 and both
files at `q8_0`: the prompt pass over the four launches of each cell, where the NVFP4 file reads
1.79 of the Q4 file, and the write rate by the mean of twelve texts, 0.943, for 1,000 tokens
written.

| handoff prompt | the prompt pass as a share of the Q4 file's reply | NVFP4 reply time over Q4 reply time |
| --- | --- | --- |
| 900 tokens, about what the handoffs of 2026-11-21 sent | 0.04 | 1.04 |
| 10,863 tokens, the largest prompt of [a full history window](history-window.md) | 0.32 | 0.90 |

With the write rate at either end of its two standard errors the two ratios read 0.98 to 1.11
and 0.86 to 0.95; with the NVFP4 file at `f16` they are 1.02 and 0.89. Two things are left out.
The load is the larger part of a handoff and is drawn in
[what the Qwen NVFP4 file writes](nvfp4-deep-counts.md#a-handoff-through-the-brain) and in
[model swap](model-swap.md#a-handoff-on-the-deep-pick). The first prompt pass after a load is
not what these rows time: they time a server that has answered before, and the one handoff drawn
on each file read that first pass 1.8 times as long on the NVFP4 file, on rows of two dates
([R-1290](../refinements/tasks/1290-the-qwen-nvfp4-files-first-prompt-pass-after-a-load-is-slower-in-one-handoff.md)).

## gemma-4-31B at 16K, split with RAM

**2026-11-22**, after the Qwen rows. Neither gemma file fits whole, so each runs as the baseline
drew it, with `--fit on`, 8 threads and the 16-bit cache: four runs of the baseline's driver in
turn (Q4, NVFP4, NVFP4, Q4), each a no-draft row and a row at draft length 1 with the Q4 file's
drafter. A cell is the mean of its two launches of three texts.

| | gemma NVFP4 | gemma Q4 |
| --- | --- | --- |
| layers on the card, without and with the drafter | 53 and 51 | 55 and 53 |
| highest reading above the floor, no draft | 17,861 and 17,865 MiB | 17,699 and 17,700 MiB |
| draft length 1 over no draft | 0.98 | 1.25 |
| drafted tokens accepted at draft length 1 | 0.59 | 0.81 |
| a cell's two launches apart, without and with the drafter | 0.009 and 0.005 | 0.036 and 0.016 |
| lowest single power limit reading, of the card's maximum | 0.80 to 0.84 | 0.87 to 0.88 |

| draft | NVFP4 rate over Q4 rate | prompt pass, NVFP4 over Q4 |
| --- | --- | --- |
| none | 0.850 | 1.19 |
| 1 | 0.667 | 1.14 |

Both rate ratios are further under 1 than any two launches of a cell sit apart. Every row has a
median power limit of 0.89 of the card's maximum, so no ratio divides rows at two median limits,
and both launches of a file ended on the same placement. Every row keeps the 1,536 MiB free.

Method: `tools/bench3.py --models gemma-4-31B --kind moe --ctx 16384 --phase deep --nmax 1` and
the same for `gemma-4-31B-NVFP4`, under `measurements/model-baseline-2026-11-16/`, rows in
`bench/pair-split-2026-11-22.jsonl` (8 measured rows among its placement checks).

## What these rows do not say

- Nothing at another context than 16K. The largest contexts and the ratios at 20K to 40K are in
  [the NVFP4 files for the deep tier](nvfp4-deep-tier.md) and divide rows of two nights.
- Nothing finer than the two standard errors above. Twelve texts a file do not tell a difference
  of less than 0.06 between the two Qwen files from none.
- Nothing about the first prompt pass after a load (R-1290), or about the gemma NVFP4 file with
  every layer on the card, the shape the stack starts the tier in.
