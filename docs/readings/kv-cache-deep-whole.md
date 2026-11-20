# Readings: the deep tier as the model host starts it, at both cache types

The draw
[R-1260](../refinements/tasks/1260-the-deep-picks-file-has-no-cache-type-row-in-the-shape-the-stack-starts.md)
asks for: the deep pick's file, gemma-4-31B in Q4, started by the model host with every layer on
the card, once with the engine's 16-bit KV cache (`f16`) and once with `q8_0`. The rule a tier
must meet to be given `q8_0` is in [the first cache type readings](kv-cache-types.md). Memory is
in MiB and stays absolute. A rate is a ratio, and every ratio divides two rows of one draw.

## What was drawn

**2026-11-20**, engine build b12375 from the `cortex-model-host` image, on the 24 GB card
(24,463 MiB) beside the desktop's apps. The model host starts from the repo's compose files with
`CORTEX_MODEL_FILE_BRAIN` naming `gemma-4-31B-it-qat-UD-Q4_K_XL.gguf` and every deep setting at
its default: 16K, `-ngl 99`, one slot. Four launches, in this order: `f16` without a drafter,
`q8_0` without one, `f16` with `mtp-gemma-4-31B-it-Q8_0.gguf` at draft length 3, `q8_0` with it.
The four were drawn twice, each launch fresh, so the record has two draws of four rows.

Method, under `measurements/model-baseline-2026-11-16/`, which git ignores:
`q8-probes/deepwhole.py <label> f16|q8_0 none|mtp` stops the cortex over the control API, reads
the card (the floor), starts the deep tier over the control API and waits for `ready`. It then
sends one warm-up, three short prompts, and a prompt of 15,896 tokens after which 256 tokens are
written, with seeds 7, 8 and 9; the rate is the median of the three. Rows are in
`bench/deep-whole-2026-11-20.jsonl` (lines 1 to 4 the first draw, 5 to 8 the second), and
`q8-probes/dw2.py` prints both draws.

The argv of the `q8_0` launches adds `--cache-type-k q8_0 --cache-type-v q8_0`, and with the
drafter `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0`. No launch has `--fit`, `-fa` or a
thread count. The engine's own projection with every layer on the card at 16K is 19,137 MiB at
`f16` and 18,064 MiB at `q8_0`, without the drafter
(`bench/deep-whole-projection-2026-11-20.json`).

## What was written before the rows

- **Fits**: with the desktop's apps counted as at least 4,750 MiB, 1,536 MiB or more is free at
  the highest reading. That is the baseline's budget of 18,177 MiB for models.
- **Whole on the card but over the budget**: the reading at load is inside 300 MiB of the
  engine's projection, the floor after the tier stops is inside 150 MiB of the floor before, and
  the rates are those of a whole model.
- **Spilled into host RAM**: the rate on a filled context or on short prompts is under 0.75 of
  the other type's row, or the prompt pass under 0.5 of it.
- **The pass mark of the second draw**, written before its first launch: the `q8_0` rate on a
  filled context is 0.90 or more of the `f16` rate in both drafter settings, and the `q8_0`
  launch reads at least 250 MiB less at its highest reading in both.

## The rows

Memory in MiB. "Free by the budget" is the row's `spare_peak`: the card less 4,750 MiB less the
highest reading above the floor read after the tier stopped; 1,536 MiB is needed.

| draw | type | drafter | floor before and after | at load above the floor | highest above the floor | free by the budget |
| --- | --- | --- | --- | --- | --- | --- |
| first | `f16` | none | 4,247 and 3,546 | 18,724 | 18,742 | 270 |
| first | `q8_0` | none | 3,542 and 3,546 | 18,355 | 18,384 | 1,333 |
| first | `f16` | length 3 | 3,547 and 3,250 | 19,518 | 19,538 | 122 short of none |
| first | `q8_0` | length 3 | 3,252 and 3,247 | 19,062 | 19,084 | 624 |
| second | `f16` | none | 3,282 and 3,282 | 19,425 | 19,443 | 270 |
| second | `q8_0` | none | 3,282 and 3,288 | 18,357 | 18,375 | 1,344 |
| second | `f16` | length 3 | 3,283 and 3,221 | 19,760 | 19,774 | 123 short of none |
| second | `q8_0` | length 3 | 3,263 and 3,256 | 19,064 | 19,086 | 620 |

`q8_0` over `f16`, both rows of the same draw:

| draw | drafter | filled context | short prompts | prompt pass | highest reading |
| --- | --- | --- | --- | --- | --- |
| first | none | 0.913 | 0.945 | 1.026 | 358 MiB less |
| first | length 3 | 1.035 | 1.033 | 1.058 | 454 MiB less |
| second | none | 0.912 | 0.970 | 1.036 | 1,068 MiB less |
| second | length 3 | 1.018 | 1.033 | 1.081 | 688 MiB less |

- **The ratios repeat.** The same launch reads 0.999 to 1.016 of its first row in the second
  draw. Drafting at length 3 writes 1.85 and 1.86 times the no-draft rate at `f16` and 2.10 and
  2.08 times at `q8_0`.
- **The pass mark of the second draw is met**: 0.912 and 1.018, and 1,068 and 688 MiB less.
- **The first draw's `f16` rows understate their memory.** The floor fell by 701 MiB under the
  `f16` launch without a drafter and by 297 MiB under the one with it: the card moved that much
  of the desktop's memory off itself, and it had not come back when the night's rows ended. With
  the fall added the first draw reads 19,443 and 19,835 MiB, and the second draw, whose floor
  did not move without the drafter and fell by 62 MiB with it, reads 19,443 and 19,774 MiB. The
  `q8_0` rows read the same in both draws to 9 MiB. So the first draw's 358 and 454 MiB read
  low: with the fall added they are 1,059 and 751 MiB. Its rates are not moved by the fall: both
  no-draft rows read 1.007 of their first row in the second draw.
- **No row fits the budget, and no row has a spill's rate.** The three no-draft rows whose floor
  stayed in place are whole on the card by the test written first: 288 to 293 MiB over the
  projection at load, the floor inside 6 MiB. The first draw's `f16` row without a drafter
  passes it only with the floor's fall added (288 MiB over). The projection has no drafter in
  it, so the test has no figure for the four drafted rows: the `q8_0` ones kept their floor to
  7 MiB, and the `f16` ones are the launch of the next item. Every row is over the 18,177 MiB:
  `q8_0` by 198 to 207 MiB without the drafter and 907 to 909 MiB with it, `f16` by 1,266 MiB
  without the drafter and 1,597 MiB with it in the second draw.
- **`f16` with the drafter is at the card's limit.** The card read 23,085 and 23,057 MiB of
  24,463 at its highest. In the second draw the drafter adds 707 MiB at load at `q8_0` and 335
  MiB at `f16` while the floor fell by 62 MiB, so about 310 MiB of that launch are not accounted
  for on the card. Its rate is not a spill's by the test written first: 0.97 and 0.98 of the
  `q8_0` row. A small spill is not ruled out, and the 1.035 and 1.018 can read high by it.

## The rule applied

| condition | reading | result |
| --- | --- | --- |
| 1 accepted | all four `q8_0` launches start and reach `ready` with the type in their argv, with no flash attention flag, which is the engine's `auto`; at load the second draw's `q8_0` launch reads 1,068 MiB less, where the engine projects 1,073 MiB less | the start is met; the log line the rule names is not shown, because the model host's log at its level has no line that names the type, so the argv and the memory are read in its place |
| 2 gain | at draft length 3, the length the tier ships with, 454 and 688 MiB less; without the drafter 358 and 1,068 MiB less | met |
| 3 rate | without drafting 0.913 and 0.912; at draft length 3 1.035 and 1.018; prompt pass 1.03 to 1.08 | met, by 0.012 without drafting |
| 4 output | one prompt of 4,028 tokens at temperature 0 at 8K with every layer on the card: the 8-bit reply is the 16-bit reply token for token, 119 of 119, and two 16-bit launches agree | passes |

**The deep pick's Q4 file meets conditions 2, 3 and 4 in the shape the stack starts, and
condition 1 by its argv and its memory in place of a log line.** What limits that:

- Condition 1 asks for a log that names `q8_0` for K and V. No log of this file names a cache
  type: the model host's has no such line at its level, and the log probe of 2026-11-18
  (`bench/q8-kvlog.jsonl`) drew other models. That the type is in effect is read from the
  memory: 1,068 MiB less at load in the second draw, against the 1,073 MiB between the
  engine's two projections.
- The no-draft rate passes the 0.90 of condition 3 by 0.012, in two draws that agree to 0.001.
  One fixed launch drawn eight times the same night spread by 0.034 of its fastest row
  ([the rows of 2026-11-20](kv-cache-remaining-cells.md)), so one launch per row cannot tell
  0.912 from 0.90. With the drafter, which is how the tier ships when a drafter is named, the
  ratio is above 1.
- Condition 3 asks for the best 8-bit draft length. Only length 3 was drawn.
- 16K is the one context drawn. The output check ran at 8K with `-fa on` named
  (`tools/q8-output.py gemma-4-31B`, rows 32 to 34 of `bench/q8-output.jsonl`).
- The desktop's apps held 3,221 to 4,247 MiB, under the 4,750 MiB the budget counts. With 4,750
  MiB counted, `f16` with the drafter needs more than the card has and `q8_0` with it leaves 620
  MiB free.

The rule decides the type only. Neither type leaves the 1,536 MiB free at 16K with every layer
on the card, so the tier's context or placement is a separate question, and R-1260 keeps it. No
default is changed by this record; the setting is built as its own change.
