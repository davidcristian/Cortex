# Readings: the model baseline at an 8-bit KV cache

The tables of [the model baseline](model-baseline.md) drawn again with `--cache-type-k q8_0
--cache-type-v q8_0`: every model that baseline drew and the two NVFP4 files, at draft lengths 0
to 6. This record has how the rows were drawn, the units and the summary at the largest context.
[The rows](model-baseline-q8-rows.md) have one table per model and tier.

The rule a tier must meet to be given the 8-bit type, its result per tier, the output check and
the night factors are in the cache type records and are not repeated here:
[the first readings](kv-cache-types.md), [every model inside one night](kv-cache-every-model.md),
[the deep tier held whole](kv-cache-deep-whole.md),
[the remaining cells](kv-cache-remaining-cells.md) and
[Qwen3.8-Flash-Next](kv-cache-flash-next.md). Those records compare chosen cells. This one has
every kept 8-bit row in the baseline's own tables.

## How the rows were drawn

**2026-11-18 to 2026-11-21**: 51 kept rows of 2026-11-18, 270 of 2026-11-19, 55 of 2026-11-20
and 6 of 2026-11-21, on the build, the budget, the rate and the draft ladder of the model
baseline. What differs from it:

- **Cache flags.** An 8-bit row adds `--cache-type-k q8_0 --cache-type-v q8_0`, and a row that
  drafts adds `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0`. The rows with an 8-bit model
  cache and a 16-bit drafter cache are not in these tables; the cache type records have them.
- **gemma-4-E4B runs with flash attention on**, on the card and on the CPU, because the engine
  does not start an 8-bit V cache with it off ([the first readings](kv-cache-types.md), group 1).
  The baseline drew the model with it off. So its 16-bit rows with it on are drawn here too, and
  they are the first table of the rows.
- **More shapes of the deep files.** gemma-4-31B has one row held whole, at 12K, beside its rows
  split with RAM. Qwen3.8-27B has rows split with RAM at 64K beside its rows held whole. The two
  NVFP4 files have tables of their own.
- **Which row is kept.** The last measured row of each model, shape, context and draft length,
  as in the baseline. Some launches were drawn on two or three dates, so a figure here can
  differ from the cache type records, which name the date of each ratio: gemma-4-12B at 64K
  without drafting reads 0.86 here, on rows of 2026-11-20, and 0.85 there, on rows of 2026-11-19.

Method, under `measurements/model-baseline-2026-11-16/`, which git ignores: `tools/bench3.py --kv
q8_0 --out q8.jsonl` and the probes the cache type records name. The 8-bit rows are in
`bench/q8.jsonl` (624 lines, 382 of them kept rows) and the 16-bit rows of the same dates in
`bench/q8-ref.jsonl` (161 lines). `q8.md` there has every kept row with its absolute rate under
"8-bit rows as baseline tables", written by `tools/q8-report.py`. `python3 tools/repo-tables.py
q8-summary q8-rows-small q8-rows-deep` prints every table of this record and of the rows record
from that row selection, and with `--check` and the two files it reports each printed line the
files do not have.

## The units

No rate is written here. The baseline's own no-draft figure for a cell is its level in units of
[the anchor row](model-baseline.md#the-anchor-row), and the figures here are ratios beside it.

- **The draft length columns** are each over the 8-bit no-draft rate of the same row of the table.
- **The no-draft column** is the 8-bit no-draft rate over the 16-bit no-draft rate of the same
  model, shape, context and flash attention setting **of the same date**, and the prompt pass
  column divides the same two rows. The 16-bit row is the last one of that date in
  `bench/q8-ref.jsonl` or `bench/q8.jsonl`.
- **An empty no-draft cell has no 16-bit row of its date.** No 8-bit row is divided by a 16-bit
  row of another date. Of the 75 no-draft rows at 8 bits, 37 have a 16-bit row of their date and
  38 do not; the sentence under each table of the rows names the contexts, and
  [R-1270](../refinements/tasks/1270-some-cache-type-cells-have-no-row-beside-a-16-bit-row-of-their-own-night.md)
  lists the cells still to draw.
- **A draft ladder can mix dates.** The "drawn" column is the date of the no-draft row, then each
  draft length drawn on another date. 8-bit launches drawn on two nights read 1.05 to 1.11 times
  their earlier rows ([every model inside one night](kv-cache-every-model.md)), so a draft figure
  whose two rows are of two dates includes the difference between those dates.
- **The 16-bit table of gemma-4-E4B with flash attention on** has no 8-bit row to divide. Its
  no-draft and prompt pass columns are over the anchor launch drawn on the same date, gemma-4-12B
  at 64K without drafting at 16 bits, which `bench/q8-ref.jsonl` has for 2026-11-19 and not for
  2026-11-18.
- **A level on this card** is the baseline's no-draft figure for the cell times the ratio here.
  That product joins rows of two dates, and the night factors say by how much such rows differ.

## Summary at the largest context

The largest context with a drafted row that fits, and a larger one drawn without drafting, as in
the baseline's summary. A model split with RAM has every context it was drawn at. "No drafted
row" is a context where no draft length was drawn or none fits.

| tier | model | context | drawn | memory, no drafter | memory, drafter | no draft, 8-bit over 16-bit of its date | best draft length, over the row's no-draft rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subagent | gemma-4-E4B, flash attention on, 16-bit rows, held whole on the card | 128K | 2026-11-19 | 5,123 MiB | 5,357 MiB | 1.17 | length 4, 1.43 |
| subagent | gemma-4-E4B, flash attention on, held whole on the card | 128K | 2026-11-19 | 4,655 MiB | 5,401 MiB | 0.58 | length 3, 1.51 |
| subagent | Qwen3.5-4B, held whole on the card | 256K | 2026-11-19 | 8,718 MiB | 10,956 MiB |  | length 3, 1.25 |
| subagent | Qwen3.5-2B, held whole on the card | 256K | 2026-11-20 | 4,011 MiB | 5,233 MiB | 0.92 | no draft (length 2 reads 0.79) |
| subagent | Qwen3.5-0.8B, held whole on the card | 256K | 2026-11-19 | 3,512 MiB | 4,684 MiB |  | no draft (length 1 reads 0.75) |
| subagent | gemma-4-E2B, held whole on the card | 128K | 2026-11-19 | 2,405 MiB | 2,891 MiB |  | length 2, 1.34 |
| chat, one E4B server | Qwen3.5-9B, held whole on the card | 256K | 2026-11-18; length 4 of 2026-11-19 | 10,979 MiB | 13,378 MiB |  | length 4, 1.35 |
| chat, one E4B server | gemma-4-12B, held whole on the card | 256K | 2026-11-19; length 1 of 2026-11-18 | 9,989 MiB | 11,551 MiB |  | length 1, 1.26 |
| chat, two E4B servers | gemma-4-12B, held whole on the card | 192K | 2026-11-18 | 9,247 MiB | 10,312 MiB |  | length 2, 1.39 |
| chat, two E4B servers | gemma-4-12B, held whole on the card | 256K | 2026-11-18 | 9,977 MiB |  |  | no drafted row |
| chat, two E4B servers | Qwen3.5-9B, held whole on the card | 160K | 2026-11-18 | 8,868 MiB | 10,521 MiB |  | length 3, 1.34 |
| chat, two E4B servers | Qwen3.5-9B, held whole on the card | 192K | 2026-11-18 | 9,572 MiB |  |  | no drafted row |
| deep | Qwen3.8-27B, held whole on the card | 48K | 2026-11-19; length 1 of 2026-11-18 | 17,217 MiB | 18,173 MiB |  | length 1, 1.08 |
| deep | Qwen3.8-27B, held whole on the card | 64K | 2026-11-19 | 17,840 MiB |  |  | no drafted row |
| deep | Qwen3.8-27B-NVFP4, held whole on the card | 48K, lengths 1 to 2 fit | 2026-11-19; length 2 of 2026-11-18 | 16,879 MiB | 18,079 MiB |  | length 2, 1.44 |
| deep | Qwen3.8-27B-NVFP4, held whole on the card | 80K | 2026-11-19 | 18,123 MiB |  |  | no drafted row |
| deep | gemma-4-31B, held whole on the card | 12K | 2026-11-19 | 18,173 MiB |  |  | no drafted row |
| deep | gemma-4-31B, split with RAM | 16K | 2026-11-19 | 17,841 MiB + 2.3 GiB RAM | 17,765 MiB + 2.0 GiB RAM | 2.10 | length 5, 1.22 |
| deep | gemma-4-31B, split with RAM | 32K | 2026-11-19 | 17,865 MiB + 2.3 GiB RAM | 17,905 MiB + 2.2 GiB RAM | 2.11 | length 3, 1.34 |
| deep | gemma-4-26B-A4B, split with RAM | 32K | 2026-11-20 | 14,657 MiB + 1.2 GiB RAM | 15,297 MiB + 1.2 GiB RAM | 0.83 | length 2, 1.32 |
| deep | gemma-4-26B-A4B, split with RAM | 64K | 2026-11-20 | 15,161 MiB + 1.2 GiB RAM | 15,957 MiB + 1.3 GiB RAM | 0.72 | length 2, 1.42 |
| deep | gemma-4-26B-A4B, split with RAM | 256K | 2026-11-19 | 17,751 MiB + 1.5 GiB RAM | 17,875 MiB + 1.8 GiB RAM | 0.69 | length 1, 1.08 |
| deep | Qwen3.6-35B-A3B, split with RAM | 256K | 2026-11-20; length 3 of 2026-11-19 | 17,786 MiB + 1.2 GiB RAM | 17,993 MiB + 1.6 GiB RAM | 0.74 | length 3, 1.27 |
| deep | gemma-4-31B-NVFP4, split with RAM | 16K | 2026-11-20 | 17,753 MiB + 2.3 GiB RAM | 17,889 MiB + 2.1 GiB RAM | 1.56 | length 3, 1.07 |
| deep | gemma-4-31B-NVFP4, split with RAM | 32K | 2026-11-20 | 17,712 MiB + 2.5 GiB RAM | 17,778 MiB + 2.3 GiB RAM | 1.94 | length 2, 1.13 |
| deep | Qwen3.8-27B, split with RAM | 64K | 2026-11-20 | 17,834 MiB + 1.2 GiB RAM | 17,997 MiB + 1.4 GiB RAM | 4.32 | no draft (length 3 reads 0.81) |
| deep | Qwen3.8-Flash-Next, split with RAM | 32K | 2026-11-21 | 17,805 MiB + 2.4 GiB RAM | 17,711 MiB + 5.7 GiB RAM | 0.94 | length 2, 1.16 |
| deep | Qwen3.8-Flash-Next, split with RAM | 256K | 2026-11-21 | 17,633 MiB + 2.1 GiB RAM |  | 1.03 (short prompts) | no drafted row |
| subagent on CPU | gemma-4-E4B, flash attention on, on the CPU | 8K | 2026-11-20 | 2.8 GiB RAM | 3.0 GiB RAM | 1.05 | no draft (length 3 reads 0.98) |
| subagent on CPU | gemma-4-E4B, flash attention on, on the CPU | 32K | 2026-11-20 | 3.1 GiB RAM |  | 0.99 (short prompts) | no drafted row |
| subagent on CPU | Qwen3.5-2B, on the CPU | 8K | 2026-11-20 | 0.9 GiB RAM | 1.0 GiB RAM | 1.01 | no draft (length 1 reads 0.87) |
| subagent on CPU | Qwen3.5-2B, on the CPU | 32K | 2026-11-20 | 1.0 GiB RAM |  | 1.01 (short prompts) | no drafted row |
| subagent on CPU | Qwen3.5-0.8B, on the CPU | 8K | 2026-11-20 | 0.3 GiB RAM | 0.4 GiB RAM | 1.00 | no draft (length 1 reads 0.84) |
| subagent on CPU | Qwen3.5-0.8B, on the CPU | 32K | 2026-11-20 | 0.5 GiB RAM |  | 1.24 | no drafted row |

Of these 34 rows, 14 have no 16-bit row of their date: the largest contexts of Qwen3.5-4B,
Qwen3.5-0.8B and gemma-4-E2B, every chat row, the four rows of the two Qwen3.8-27B files held
whole, and gemma-4-31B held whole at 12K, where the 16-bit cache does not fit. A row marked
"short prompts" divides two medians of three short prompts. The first row is the 16-bit table of
gemma-4-E4B, and its figure is over the anchor launch of its date.

## What these rows do not say

- Nothing about whether a tier should set the 8-bit type. The rule and its result are in the
  cache type records named at the top.
- Nothing about what a model writes at 8 bits beyond the output check of those records.
- Nothing about a level without the baseline's row beside it, and that row is of another date.
