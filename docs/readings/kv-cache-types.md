# Readings: an 8-bit KV cache beside the default 16-bit cache

A server holds its context in the KV cache. The engine's default type for it is `f16`, and no
server in the stack sets another. `--cache-type-k q8_0 --cache-type-v q8_0` asks for an 8-bit type
that takes about half the memory per token of context.
[R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md)
asks whether a tier should set it. This record holds the rows that decide that, beside the rows the
model baseline of 2026-11-16 drew at 16 bits. Memory is `nvidia-smi` `memory.used` at the highest
reading of a row, less what the card held before the load, and stays absolute because a reader
compares it with their own card. A rate describes only the card it was read on, so each one is
written as a ratio of the 16-bit rate at the same context and draft length.

## How the rows are drawn

**2026-11-18**, on `llama-server` build b12375 from the `cortex-model-host` image, the build of the
16-bit rows. One server at a time on the 24 GB card (24,463 MiB), started with `--parallel 1 --jinja
--cache-ram 0`, every layer on the card (`-ngl 99 --fit off`), the sampler and the flash attention
setting of the model's card. An 8-bit row adds `--cache-type-k q8_0 --cache-type-v q8_0`, and a row
that drafts adds `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0`, so the drafter's cache
follows the model's: a tier sets one type for the whole server.

- **Budget.** Models get 18,177 MiB at the highest reading of a row: the card less 4,750 MiB counted
  for the desktop's apps and 1,536 MiB kept free. A chat row also leaves 3,850 MiB for one
  gemma-4-E4B server or 7,250 MiB for two.
- **Rate.** Read while 256 tokens are written after a prompt that fills the context less 512
  tokens, as the median of three seeds. The prompt pass is the rate at which that prompt is read.
- **Draft lengths.** None, then 1 to 6. A ladder stops when the rate falls twice in a row or a
  length goes over the budget.
- **Largest context.** Searched from the top over powers of two and sums of a power of two with one
  of the next two lower powers (128K, 160K, 192K, 256K). One step of the search is the next size up
  in that list.
- **Power.** A row is kept when `enforced.power.limit` over `power.max_limit` has a median of 0.84
  or more across the row, the rule the baseline keeps a row on.

Method: `tools/bench3.py --kv q8_0 --out q8.jsonl` under `measurements/model-baseline-2026-11-16/`,
which git ignores. The 8-bit rows are in `bench/q8.jsonl` there with a `kv` field, the 16-bit rows
in `bench/baseline.jsonl` and `bench/nvfp4.jsonl`, and `q8.md` has both sets with their absolute
rates.

## What each group of rows decides

Written before any row was drawn.

| group | rows | decides | a null result |
| --- | --- | --- | --- |
| 1 | gemma-4-E4B with flash attention off, 8K and 64K | whether the build accepts `q8_0` with the setting the subagent tier runs | the server exits, or starts and its log names `f16`; then the same contexts with flash attention on, at both types, marked as off the card's setting |
| 2 | gemma-4-12B and Qwen3.5-9B with room for two gemma-4-E4B servers | the largest context with the drafter, against 160K and 128K at 16 bits | the same largest context, and under 250 MiB less memory there |
| 3 | Qwen3.5-9B and gemma-4-12B with room for one gemma-4-E4B server | the largest context of the 9B with its draft layer, against 192K; memory and rate of the 12B at 256K, against 12,424 MiB | 192K again; the 12B within 250 MiB of the 16-bit row |
| 4 | Qwen3.8-27B, the Q4 file and the NVFP4 file, alone | the largest context with the draft layer, against 24K and 32K | the same largest context |
| 5 | Qwen3.5-4B, Qwen3.5-2B, Qwen3.5-0.8B and gemma-4-E2B at 8K | memory and rate of a subagent server at the size it runs | memory within 250 MiB and rate within a tenth of the 16-bit row |
| 6 | gemma-4-12B, Qwen3.5-9B and Qwen3.8-27B, one prompt at both types | whether the reply changes | the 8-bit reply is the 16-bit reply token for token |

Group 6 is an indicator, not a measure of quality: one prompt of about 4,000 tokens, temperature 0,
one seed, no drafting, thinking off, 256 tokens written. Two 16-bit launches are compared first, so
that a difference between the types can be told from a difference between two launches. The record
gives the count of leading tokens that are identical and whether the two replies state the same
things.

## The rule a tier must meet to be given `q8_0`

Written before any row was drawn. All four conditions must hold on the rows of the tier's model. A
tier that has no row for a condition is not decided.

1. **Accepted.** The server starts with the flash attention setting the tier runs, and its log
   names `q8_0` for both K and V.
2. **Gain.** Either the largest context that fits with the drafter under the tier's budget is at
   least one step of the search above the 16-bit one, or at a context both types have a row for the
   memory at the tier's best draft length falls by 250 MiB or more. 250 MiB is the rise the driver
   allows between an idle and a working server, so a smaller fall is within what one row moves.
3. **Rate.** At every context where both types have a row, the 8-bit rate is at least 0.90 of the
   16-bit rate at the same draft length, for the no-draft row and for the best 8-bit draft length,
   and the 8-bit prompt pass is at least 0.90 of the 16-bit one. The three seeds of one baseline
   row differ by up to about a tenth of their median, so a smaller fall cannot be told from the
   spread of a row.
4. **Output.** The group 6 check of the tier's model does not fail. It fails when the 8-bit reply
   is empty, ends for another reason than the 16-bit reply, repeats itself, or states something
   that neither the 16-bit reply nor the prompt supports. Another wording of the same statements
   is not a failure.

No tier's setting changes on these rows alone: a tier that meets the rule is named here and in
R-1243, and the setting is built as its own change.

## The rows

Not drawn yet.
