# Readings: the model baseline of 2026-11-16

Every model on the models mount that a tier can run, drawn at draft lengths 0 to 6 and at each
context the tier allows, on the 24 GB card with the user's desktop apps open and the context held
in the engine's default 16-bit cache. Later measurements are compared with these rows:
[the NVFP4 files](nvfp4-deep-tier.md), [the tier drafters](tier-drafters.md) and the cache type
records that start at [the first cache type readings](kv-cache-types.md). This record has the
method, the anchor row every rate is written against, what the run found and the summary tables.
[The rows](model-baseline-rows.md) have one table per model and tier.

Memory is `nvidia-smi` `memory.used` at the highest reading of a row, less the higher of what
the card held before the load and after the unload, and stays absolute because a reader
compares it with their own card. A rate
describes only the card it was read on, so no rate is written here: each one is a ratio of
another row of this baseline.

| model | file under the models mount | drafter |
| --- | --- | --- |
| gemma-4-E4B | `unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` | `mtp-gemma-4-E4B-it-Q8_0.gguf` |
| gemma-4-E2B | `unsloth/gemma-4-E2B-it-qat-GGUF/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` | `mtp-gemma-4-E2B-it-Q8_0.gguf` |
| gemma-4-12B | `unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` | `mtp-gemma-4-12B-it-Q8_0.gguf` |
| Qwen3.5-9B | `unsloth/Qwen3.5-9B-MTP-GGUF/Qwen3.5-9B-Q4_K_M.gguf` | its own draft layer |
| Qwen3.8-27B | `unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` | its own draft layer |
| gemma-4-31B | `unsloth/gemma-4-31B-it-qat-GGUF/gemma-4-31B-it-qat-UD-Q4_K_XL.gguf` | `mtp-gemma-4-31B-it-Q8_0.gguf` |
| gemma-4-26B-A4B | `unsloth/gemma-4-26B-A4B-it-qat-GGUF/gemma-4-26B-A4B-it-qat-UD-Q4_K_XL.gguf` | `mtp-gemma-4-26B-A4B-it-Q8_0.gguf` |
| Qwen3.6-35B-A3B | `unsloth/Qwen3.6-35B-A3B-MTP-GGUF/Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf` | its own draft layer |
| Qwen3.5-4B | `unsloth/Qwen3.5-4B-MTP-GGUF/Qwen3.5-4B-Q4_K_M.gguf` | its own draft layer |
| Qwen3.5-2B | `unsloth/Qwen3.5-2B-MTP-GGUF/Qwen3.5-2B-Q4_K_M.gguf` | its own draft layer |
| Qwen3.5-0.8B | `unsloth/Qwen3.5-0.8B-MTP-GGUF/Qwen3.5-0.8B-Q8_0.gguf` | its own draft layer |
| Qwen3.8-Flash-Next | `unsloth/Qwen3.8-Flash-Next-GGUF/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf` | `mtp-Qwen3.8-Flash-Next-Q8_0.gguf` |

The three Qwen3.5 subagent files, Qwen3.5-9B, Qwen3.8-27B and Qwen3.6-35B-A3B draft with a layer
inside their own file. The NVFP4 files of the mount are in [their own record](nvfp4-deep-tier.md).

## How the rows were drawn

**2026-11-16 to 2026-11-18.** A row's date is the date in its `time` field. The run began on
2026-11-16 and went on through the night into 2026-11-17, so the rows of those two dates are of
one run. Two rows of Qwen3.8-Flash-Next are of 2026-11-18.

- **Engine.** `llama-server` build b12375 from the `cortex-model-host` image for every row that
  uses the card. The CPU rows use `ghcr.io/ggml-org/llama.cpp:server` build b10680 in a container
  of 4 CPUs and 8 GB, with 4 threads.
- **Launch.** One server at a time, started with `--parallel 1 --jinja --cache-ram 0`, the sampler
  of the model's card and no `--cache-type-k` or `--cache-type-v`. Flash attention is on for every
  model but gemma-4-E4B, whose card says off. A model held whole on the card runs with `-ngl 99
  --fit off`. A model that does not fit whole runs with `--fit on` and 8 threads, 16 for
  Qwen3.8-Flash-Next, which keeps what fits on the card and the rest in RAM.
- **Budget.** The card has 24,463 MiB. Models get 18,177 MiB at the highest reading of a row: the
  card less 4,750 MiB counted for the desktop's apps, their median during the run, and 1,536 MiB
  kept free. A chat row also leaves at least 3,450 MiB for one gemma-4-E4B server, or 7,250 MiB
  for two.
- **Rate.** `timings.predicted_per_second` of the server's reply while 256 tokens are written
  after a prompt that fills the context less 512 tokens, as the median of three seeds. The prompt
  pass is `timings.prompt_per_second` of the first of those replies. A row marked "short prompts"
  is the median of three short prompts instead, drawn where a filled prompt pass takes too long.
- **Draft lengths.** None, then 1 to 6, one launch each. A ladder stops when the rate falls twice
  in a row or a length goes over the budget.
- **Contexts.** Subagent models at every power of two. Chat and deep models at the largest size
  that fits, searched from the top over powers of two and sums of a power of two with one of the
  next two lower powers.
- **Memory of a split model.** The card's reading, and beside it the process memory Docker reports.
- **Power.** The fans ran at their maximum, and the vendor setting that moves power between the
  processor and the card was set to one low value for the whole run. `enforced.power.limit` over
  `power.max_limit` moves between 0.80 and 0.89. A row held whole on the card is kept when the
  ratio stayed at 0.84 or more for most of the row; the same row at 0.80 reads 0.70 to 0.93 of
  its kept rate.

Method: `tools/bench3.py` under `measurements/model-baseline-2026-11-16/`, which git ignores, one
`--phase` per tier. The rows are in `bench/baseline.jsonl` there (458 lines, 318 of them kept
rows), `bench/slots.jsonl` and `bench/together.jsonl`; `bench/superseded-rows.jsonl` has the 38
rows that were replaced, and `baseline.md` has every kept row with its absolute rate. `python3
tools/repo-tables.py` prints every table of this record and of the rows record from the row
selection of `tools/report.py`, and with `first-files first-summary first-rows --check` and the
two files it reports each printed line the files do not have.

## The anchor row

Every level in this baseline is written in units of one kept row: **gemma-4-12B at a 64K context,
no draft, 16 bits, drawn on 2026-11-16** with room kept for one subagent server (`--ctx-size 65536
--parallel 1 --jinja --cache-ram 0 -fa on -ngl 99 --fit off`, 8,381 MiB). It is the launch
`q8-probes/drift.py` draws again on later nights for
[R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md).
Its three seeds read 0.99 to 1.01 of their median.

- **The no-draft column** of every table is the row's rate over the anchor's rate. A row of short
  prompts is over the anchor's own short prompts, which read 1.21 times its filled rate.
- **The draft length columns** are each over the no-draft rate of the same row of the table.
- **The prompt pass column** is the row's prompt pass over the anchor's.
- **A reader on other hardware** draws the anchor launch and multiplies.
- **Two dates.** The anchor is of 2026-11-16. A no-draft or prompt pass figure of a row of another
  date divides rows of two dates, and each table says where. The same launch has read 1.06 to
  1.23 times its earlier rate on a later night, and the anchor launch read 1.15 times this row on
  2026-11-19 ([the cache type rows of every model](kv-cache-every-model.md)). That factor was
  read between nights and not between the two dates of this run. A draft length column divides
  two rows of one ladder, and the "drawn" column names each length drawn on another date than
  the no-draft row.

## What the run found

- **Two subagents beside the chat model fit in both shapes.** gemma-4-12B at 256K with one
  gemma-4-E4B server of two 16K slots, or at 160K with two gemma-4-E4B servers of 8K each. Both
  were loaded together and checked (the last table below).
- **The best draft length is 2 or 3 for gemma-4-E4B and gemma-4-E2B, and 3 or 4 for Qwen3.5-4B
  and Qwen3.5-9B.** gemma-4-12B does best at 3 up to 160K, at 2 at 192K and at 1 at 256K.
  Qwen3.8-27B does best at 5 where that fits. The gemma cards' value of 4 and the Qwen cards'
  value of 6 are the best at no context.
- **Qwen3.5-2B and Qwen3.5-0.8B are slower with drafting at every context**, on the card and on
  the CPU. On the CPU only gemma-4-E4B gains, and only at draft length 3.
- **gemma-4-31B does not fit whole at any context at 16 bits.** Split with RAM it writes 0.15 of
  the anchor's rate at 16K and 0.10 at 32K. Qwen3.8-27B fits whole up to 24K with drafting and
  40K without.
- **gemma-4-26B-A4B and Qwen3.6-35B-A3B, split with RAM, run their full 256K context** at 0.73
  and 0.69 of the anchor's rate, and their best draft lengths add 1.04 and 1.12 times.
- **A nearly full card pushes other apps' memory off it.** Loading to about 22.3 GB in total
  made the memory other apps held fall from 4,583 to 3,440 MiB. A fit check that reads free
  memory then passes when it should fail, which is why other apps are counted at a fixed figure.
- **gemma-4-E4B needs more card memory while it works than when it is idle**: about 170 MiB more
  at 8K, 400 at 32K and 1,200 at 128K. The other models rise by 250 MiB at most.
- **gemma-4-E4B is faster with flash attention on**, which its card says to turn off. One check
  at 64K and draft length 2 read about 1.3 times the rate, 1.2 times the prompt pass and 1.7 GB
  less card memory. The rows here keep the card's setting. The stack passes no flash attention
  flag, and the engine then turns it on ([the first cache type readings](kv-cache-types.md),
  group 1). [The rows at an 8-bit cache](model-baseline-q8-rows.md) begin with the 16-bit ladder
  drawn with it on. No reply with it on was compared with a reply with it off.
- **The gemma-4-E4B prompt pass with flash attention off read 0.29 of its first value on
  2026-11-17**, at 64K, while the card stayed nearly idle. The cause is not known. Every
  gemma-4-E4B row here is of 2026-11-16. A check after the machine was restarted on 2026-11-17
  read 0.87 of the first value (`HANDOFF.md` in the measurement folder).
- **Qwen3.8-Flash-Next needs its weights in memory.** With the containers' Linux host capped at
  32 GB of memory the engine left 97.5 GiB of weights off the card, more than that memory, and
  every token read from the models mount: the file wrote 0.14 of the rate it writes with the cap
  at 96 GB. With that cap, 8 threads read 0.95 of the rate at 16 threads and 24 threads 0.35. A
  filled pass at 256K takes too long and was not drawn, so the 256K rows are short prompts.
- **Drafting was slower at every length for Qwen3.8-Flash-Next.** The ladder at a filled 32K was
  completed on 2026-11-18 and reads 0.99, 0.93 and 0.85 at draft lengths 1 to 3. The 16-bit rows
  of 2026-11-21 read the other way at 32K, 1.04 at length 1 and 1.11 at length 2
  ([the cache type rows of Qwen3.8-Flash-Next](kv-cache-flash-next.md)).

## Summary at the largest context

| tier | model | context | drawn | memory, no drafter | memory, drafter | no draft, over the anchor | best draft length, over the row's no-draft rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subagent | gemma-4-E4B, held whole on the card | 128K | 2026-11-16 | 8,512 MiB | 9,930 MiB | 0.48 | length 2, 1.85 |
| subagent | gemma-4-E2B, held whole on the card | 128K | 2026-11-16 | 2,558 MiB | 2,835 MiB | 1.83 | length 2, 1.17 |
| subagent | Qwen3.5-4B, held whole on the card | 256K | 2026-11-17 | 11,543 MiB | 13,223 MiB | 0.70 | length 3, 1.53 |
| subagent | Qwen3.5-2B, held whole on the card | 256K | 2026-11-17 | 4,967 MiB | 5,883 MiB | 1.51 | no draft (length 1 reads 0.94) |
| subagent | Qwen3.5-0.8B, held whole on the card | 256K | 2026-11-17 | 4,483 MiB | 5,345 MiB | 1.64 | no draft (length 1 reads 0.83) |
| chat, one E4B server | gemma-4-12B, held whole on the card | 256K | 2026-11-17 | 11,786 MiB | 12,424 MiB | 0.78 | length 1, 1.28 |
| chat, one E4B server | Qwen3.5-9B, held whole on the card | 192K | 2026-11-17 | 11,727 MiB | 13,191 MiB | 0.73 | length 3, 1.57 |
| chat, one E4B server | Qwen3.5-9B, held whole on the card | 256K | 2026-11-17 | 13,841 MiB |  | 0.60 | drafting does not fit |
| chat, two E4B servers | gemma-4-12B, held whole on the card | 160K | 2026-11-17 | 10,025 MiB | 10,761 MiB | 0.91 | length 3, 1.55 |
| chat, two E4B servers | gemma-4-12B, held whole on the card | 192K | 2026-11-17 | 10,565 MiB |  | 0.83 | drafting does not fit |
| chat, two E4B servers | Qwen3.5-9B, held whole on the card | 128K | 2026-11-17 | 9,611 MiB | 10,755 MiB | 0.84 | length 3, 1.58 |
| chat, two E4B servers | Qwen3.5-9B, held whole on the card | 160K | 2026-11-17 | 10,667 MiB |  | 0.77 | drafting does not fit |
| deep | Qwen3.8-27B, held whole on the card | 24K, lengths 1 to 3 fit | 2026-11-17 | 16,931 MiB | 18,023 MiB | 0.50 | length 3, 1.75 |
| deep | Qwen3.8-27B, held whole on the card | 40K | 2026-11-17 | 17,973 MiB |  | 0.48 | drafting does not fit |
| deep | gemma-4-31B, split with RAM | 16K | 2026-11-17 | 17,727 MiB + 4.0 GiB RAM | 17,745 MiB + 3.3 GiB RAM | 0.15 | length 1, 1.24 |
| deep | gemma-4-31B, split with RAM | 32K | 2026-11-17 | 17,887 MiB + 4.2 GiB RAM | 17,765 MiB + 3.8 GiB RAM | 0.10 | no draft (length 1 reads 0.85) |
| deep | gemma-4-26B-A4B, split with RAM | 256K | 2026-11-17 | 17,886 MiB + 1.9 GiB RAM | 17,801 MiB + 2.0 GiB RAM | 0.73 | length 1, 1.04 |
| deep | Qwen3.6-35B-A3B, split with RAM | 256K | 2026-11-17 | 17,941 MiB + 1.2 GiB RAM | 18,076 MiB + 1.6 GiB RAM | 0.69 | length 2, 1.12 |
| deep | Qwen3.8-Flash-Next, split with RAM | 32K | 2026-11-17 | 17,531 MiB + 2.4 GiB RAM | 17,581 MiB + 9.7 GiB RAM | 0.33 | no draft (length 1 reads 0.99) |
| deep | Qwen3.8-Flash-Next, split with RAM | 256K | 2026-11-17 | 17,991 MiB + 2.3 GiB RAM | 17,786 MiB + 7.8 GiB RAM | 0.25 (short prompts) | no draft (length 1 reads 0.84) |
| subagent on CPU | gemma-4-E4B, on the CPU | 8K | 2026-11-17 | 3.1 GiB RAM | 3.2 GiB RAM | 0.15 | length 3, 1.09 |
| subagent on CPU | gemma-4-E4B, on the CPU | 16K | 2026-11-17 | 3.1 GiB RAM |  | 0.14 (short prompts) | the prompt pass is too long |
| subagent on CPU | Qwen3.5-2B, on the CPU | 16K | 2026-11-17 | 1.0 GiB RAM | 1.2 GiB RAM | 0.17 | no draft (length 1 reads 0.72) |
| subagent on CPU | Qwen3.5-2B, on the CPU | 32K | 2026-11-17 | 1.2 GiB RAM |  | 0.24 (short prompts) | the prompt pass is too long |
| subagent on CPU | Qwen3.5-0.8B, on the CPU | 32K | 2026-11-17 | 0.7 GiB RAM | 1.0 GiB RAM | 0.12 | no draft (length 1 reads 0.72) |

## Subagent models at 8K, the default subagent context

| tier | model | context | drawn | memory, no drafter | memory, drafter | no draft, over the anchor | best draft length, over the row's no-draft rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| subagent | gemma-4-E4B, held whole on the card | 8K | 2026-11-16 | 3,351 MiB | 3,579 MiB | 1.82 | length 3, 1.60 |
| subagent | gemma-4-E2B, held whole on the card | 8K | 2026-11-16 | 1,699 MiB | 1,841 MiB | 2.96 | length 3, 1.51 |
| subagent | Qwen3.5-4B, held whole on the card | 8K | 2026-11-17 | 3,349 MiB | 3,819 MiB | 1.90 | length 3, 1.37 |
| subagent | Qwen3.5-2B, held whole on the card | 8K | 2026-11-17 | 1,735 MiB | 1,973 MiB | 3.20 | no draft (length 3 reads 0.92) |
| subagent | Qwen3.5-0.8B, held whole on the card | 8K | 2026-11-17 | 1,217 MiB | 1,391 MiB | 3.89 | no draft (length 2 reads 0.86) |
| subagent on CPU | gemma-4-E4B, on the CPU | 8K | 2026-11-17 | 3.1 GiB RAM | 3.2 GiB RAM | 0.15 | length 3, 1.09 |
| subagent on CPU | Qwen3.5-2B, on the CPU | 8K | 2026-11-17 | 0.9 GiB RAM | 1.1 GiB RAM | 0.24 | no draft (length 1 reads 0.80) |
| subagent on CPU | Qwen3.5-0.8B, on the CPU | 8K | 2026-11-17 | 0.4 GiB RAM | 0.5 GiB RAM | 0.33 | no draft (length 1 reads 0.77) |

## Two subagents beside the chat model

One gemma-4-E4B server with a 16K pool, by slot count:

| slots | drafter | memory at start | context per slot | one request, over the anchor | both slots busy, over the anchor |
| --- | --- | --- | --- | --- | --- |
| 1 | draft length 3 | 3,743 MiB | 16K | 2.80 |  |
| 2 | none | 3,402 MiB | 8K | 2.03 | 1.67 and 1.81 |
| 2 | draft length 3 | 3,609 MiB | 8K | 2.94 | 1.99 and 1.97 |

The chat model and its subagents loaded at once, every context filled and every server busy:

| shape | drawn | chat model | subagents | all at the highest reading | free there | chat rate over the anchor, subagents idle | the same, subagents busy | each subagent meanwhile, over the anchor |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12B at 256K, one E4B server with two slots of 16K | 2026-11-17 | 12,388 MiB | 4,056 MiB | 16,659 MiB | 3,054 MiB | 0.98 | 0.79 | 1.07 and 1.55 |
| 12B at 160K, two E4B servers of 8K | 2026-11-17 | 10,661 MiB | 3,387 + 3,389 MiB | 17,678 MiB | 2,035 MiB | 1.39 | 0.78 | 1.50 and 1.34 |

In the first table the slot rows have no `time` field; their run ended on 2026-11-16. The rows
of the second table are of 2026-11-17 and divide by the anchor of 2026-11-16.

## What these rows do not say

- Nothing about what a model writes: no stop row, reasoning count or injection row is here.
- Nothing about another cache type. [The baseline at an 8-bit cache](model-baseline-q8.md) has
  the same tables drawn with `--cache-type-k q8_0 --cache-type-v q8_0`.
- Nothing about a rate on another night. A level here is the anchor's rate of 2026-11-16 times a
  ratio, and
  [R-1259](../refinements/tasks/1259-the-same-launch-reads-a-different-rate-on-another-night.md)
  has what is known about the difference between nights.
