# Readings: an 8-bit KV cache beside the default 16-bit cache

A server holds its context in the KV cache. The engine's default type for it is `f16`, which every
server but the deep tier's starts at. `--cache-type-k q8_0 --cache-type-v q8_0` asks for an 8-bit
type that takes about half the memory per token of context.
[R-1243](../refinements/tasks/1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md)
asks whether a tier should set it. This record holds the rows that decide that, beside the 16-bit
rows of [the model baseline of 2026-11-16](model-baseline.md). Memory is `nvidia-smi`
`memory.used` at the highest reading of a row, less what the card held before the load, and stays
absolute because a reader compares it with their own card. A rate describes only the card it was
read on, so each one is written as a ratio of the 16-bit rate at the same context and draft length.

## How the rows are drawn

**2026-11-18**, on `llama-server` build b12375 from the `cortex-model-host` image, the build of the
16-bit rows. One server at a time on the 24 GB card (24,463 MiB), started with `--parallel 1 --jinja
--cache-ram 0`, every layer on the card (`-ngl 99 --fit off`), the sampler and the flash attention
setting of the model's card. An 8-bit row adds `--cache-type-k q8_0 --cache-type-v q8_0`, and a row
that drafts adds `--cache-type-k-draft q8_0 --cache-type-v-draft q8_0`, so in these rows the
drafter's cache followed the model's ([which type a tier's drafter takes](drafter-cache.md)).

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
| 1 | gemma-4-E4B with flash attention off, 8K and 64K | whether the build accepts `q8_0` with the model card's setting | the server exits, or starts and its log names `f16`; then the same contexts with flash attention on, at both types, marked as off the card's setting |
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

**2026-11-18.** Each model's output check was drawn while its file was loaded for its own group.
The short rows were drawn again for the power rule. Every row in these tables then has a median
ratio of 0.84 or more, except three 8K rows between 0.82 and 0.84: the 16-bit gemma-4-E4B row at
draft length 3 and the 8-bit rows of Qwen3.5-4B and Qwen3.5-2B without drafting.

### Group 1: gemma-4-E4B

With flash attention off the server does not start, at 8K or at 64K. It exits while it creates the
context and logs `llama_init_from_model: quantized V cache requires flash_attn to be enabled`. With
`--cache-type-k q8_0` alone and V at 16 bits it starts, at 3,179 MiB at load at 8K against 3,213
MiB, and was not measured further.

The stack passes no flash attention flag, so its servers run the engine's `auto`
([R-1240](../refinements/tasks/1240-some-tiers-run-settings-their-model-cards-do-not-recommend.md)).
With `auto` and 16 bits the engine logs `resolve_fused_ops: Flash Attention enabled`. With `auto`
and `q8_0` it starts, logs `enabling flash_attn since it is required for quantized V cache`, and
names `K (q8_0)` and `V (q8_0)`. So the rows with flash attention on are the subagent tier as the
stack runs it, and off is the model card's setting. Both types with it on, without drafting and at
the best draft length of the 16-bit rows:

| context | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- | --- | --- |
| 8K | none | 3,072 MiB | 3,029 MiB | 0.93 | 0.95 |
| 8K | 3 | 3,193 MiB | 3,175 MiB | 0.94 | 0.95 |
| 64K | none | 4,041 MiB | 3,790 MiB | 0.67 | 0.96 |
| 64K | 2 | 4,199 MiB | 4,212 MiB | 0.74 | 0.95 |

The baseline's 16-bit rows with flash attention off read 3,351 and 3,575 MiB at 8K and 5,764 and
6,466 MiB at 64K.

### Groups 2 and 3: the chat models

The largest context under each budget, with the memory of the highest row drawn there:

| model | room kept | | 16-bit | 8-bit |
| --- | --- | --- | --- | --- |
| gemma-4-12B | two servers | with the drafter | 160K, 10,761 MiB | 192K, 10,312 MiB (256K reads 11,213 MiB at load, over) |
| gemma-4-12B | two servers | without | 192K, 10,565 MiB | 256K, 9,977 MiB |
| Qwen3.5-9B | two servers | with the draft layer | 128K, 10,755 MiB | 160K, 10,521 MiB (192K reads 11,188 MiB at load, over) |
| Qwen3.5-9B | two servers | without | 160K, 10,670 MiB | 192K, 9,572 MiB (256K reads 10,928 MiB at load, 1 MiB over) |
| Qwen3.5-9B | one server | with the draft layer | 192K, 13,191 MiB | 256K, 13,225 MiB at draft length 3 |
| Qwen3.5-9B | one server | without | 256K, 13,841 MiB | 256K, 10,979 MiB |
| gemma-4-12B | one server | with the drafter | 256K, 12,424 MiB | 256K, 11,245 MiB |

The same context and draft length at both types:

| model | context | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- | --- | --- | --- |
| gemma-4-12B | 192K | none | 10,565 MiB | 9,247 MiB | 0.73 | 1.06 |
| gemma-4-12B | 192K | 1 | 11,263 MiB | 10,305 MiB | 0.75 | 1.03 |
| gemma-4-12B | 192K | 2 | 11,260 MiB | 10,307 MiB | 0.73 | 1.03 |
| gemma-4-12B | 192K | 4 | 11,255 MiB | 10,312 MiB | 0.75 | 1.08 |
| gemma-4-12B | 256K | none | 11,786 MiB | 9,977 MiB | 0.66 | 1.02 |
| gemma-4-12B | 256K | 1 | 12,413 MiB | 11,245 MiB | 0.70 | 1.04 |
| gemma-4-12B | 256K | 2 | 12,424 MiB | 11,231 MiB | 0.70 | 1.04 |
| Qwen3.5-9B | 160K | none | 10,670 MiB | 8,868 MiB | 0.90 | 0.98 |
| Qwen3.5-9B | 192K | none | 11,727 MiB | 9,572 MiB | 0.87 | 0.97 |
| Qwen3.5-9B | 192K | 3 | 13,087 MiB | 11,355 MiB | 0.67 | 0.97 |
| Qwen3.5-9B | 256K | none | 13,841 MiB | 10,979 MiB | 0.90 | 0.97 |

The 192K ladder of gemma-4-12B is whole (draft length 3 reads 0.76), and its best length is 2 at
both types. At 256K with room for one server the 8-bit rows are draft lengths 1 and 2 for
gemma-4-12B and none, 1 and 3 for Qwen3.5-9B.

- **The largest context rises by one step in every shape the budget decided at 16 bits**, and at a
  context both types hold the memory falls by 943 to 2,862 MiB.
- **The rate on a filled context falls.** gemma-4-12B writes 0.66 to 0.76 of its 16-bit rate, with
  and without its drafter. Qwen3.5-9B writes 0.87 to 0.90 without drafting and 0.67 at draft length
  3. The short prompts of the same launches, which leave the context nearly empty, read 0.95 to
  1.00 without drafting, so the fall grows with what the context holds. The prompt pass does not
  change (0.97 to 1.08).
- **A larger context at 8 bits is slower than the smaller one at 16.** The best 8-bit rate at the
  new largest context over the best 16-bit rate at the old one is 0.60 for gemma-4-12B with two
  servers, 0.70 for Qwen3.5-9B with two servers and 0.58 for Qwen3.5-9B with one.
- **Drafting adds more memory at 8 bits than at 16**: at 192K, 1,058 MiB against 698 MiB for
  gemma-4-12B at draft length 1 and 1,783 MiB against 1,360 MiB for Qwen3.5-9B at draft length 3.
  The log gives the draft cache itself at about half its 16-bit size. With the drafter's cache
  left at 16 bits (`--kv-draft f16` in the driver) nothing changes for gemma-4-12B: 256K still
  reads 11,223 MiB at load, and 192K at draft length 2 reads the same memory and rate. Qwen3.5-9B
  takes 354 to 556 MiB less (192K reads 10,765 MiB at load, which fits beside two servers) and
  writes 1.04 times its 8-bit rate at 160K and draft length 3.

### Group 4: Qwen3.8-27B

| file | | 16-bit | 8-bit |
| --- | --- | --- | --- |
| Q4 | largest context with the draft layer | 24K, draft lengths 1 to 3 (18,023 MiB at 3) | 48K, draft length 1 only (18,173 MiB; 2 reads 18,291 MiB at load, over) |
| Q4 | largest context without drafting | 40K, 17,973 MiB | 64K, 17,830 MiB (80K reads 18,437 MiB at load, over) |
| NVFP4 | largest context with the draft layer | 32K, draft length 1 only (18,104 MiB) | 48K, draft lengths 1 and 2 (18,079 MiB at 2; 3 reads 18,234 MiB, over) |
| NVFP4 | largest context without drafting | 40K, 17,709 MiB | 80K, 18,126 MiB (96K reads 18,691 MiB at load, over) |

The Q4 file where the 16-bit cache has a ladder:

| context | draft length | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit | prompt pass, 8-bit over 16-bit |
| --- | --- | --- | --- | --- | --- |
| 16K | none | 16,409 MiB | 15,963 MiB | 1.00 | 1.07 |
| 16K | 3 | 17,465 MiB | 16,995 MiB | 0.97 | 1.07 |
| 16K | 5 | 17,766 MiB | 17,294 MiB | 0.88 | 1.13 |
| 24K | none | 16,931 MiB | 16,267 MiB | 0.97 | 1.02 |
| 24K | 1 | 17,722 MiB | 17,074 MiB | 0.91 | 1.07 |
| 24K | 2 | 17,871 MiB | 17,215 MiB | 1.00 | 1.06 |
| 24K | 3 | 18,023 MiB | 17,365 MiB | 0.95 | 1.05 |
| 24K | 4 | 18,249 MiB, over | 17,515 MiB | 1.00 | 1.09 |

At 24K every draft length fits at 8 bits (17,813 MiB at 6), and the best is 4, at 0.97 of the
best 16-bit rate, which is at draft length 3. At 16K the best 8-bit length is 3 and the best 16-bit
length is 5: the other lengths read 0.84 to 1.06, and the best 8-bit rate is 0.91 of the best
16-bit rate. The 8-bit rows above 24K have no 16-bit row at their context: 48K without drafting
reads 0.89 and 64K reads 0.82 of the 16-bit rate at 40K, and 48K at draft length 1 reads 0.75 of
the 16-bit rate at 24K and draft length 1.

The NVFP4 file at 32K, the largest context its 16-bit cache drafts at, reads 0.90 of the 16-bit
rate without drafting (16,250 MiB, 939 MiB less) and 0.81 at draft length 1 (17,195 MiB, 909 MiB
less), with the prompt pass at 0.96 and 0.97.

### Group 5: the small models at 8K

Each of the four starts with `q8_0`, and memory falls by 7 to 94 MiB, the null result the group
named. Without drafting, then at the best draft length of the 16-bit rows:

| model | draft lengths | 16-bit memory | 8-bit memory | rate, 8-bit over 16-bit |
| --- | --- | --- | --- | --- |
| Qwen3.5-4B | none, 3 | 3,349 and 3,717 MiB | 3,260 and 3,623 MiB | 0.99 and 0.96 |
| Qwen3.5-2B | none, 3 | 1,735 and 1,894 MiB | 1,686 and 1,887 MiB | 1.07 and 1.01 |
| Qwen3.5-0.8B | none, 2 | 1,217 and 1,349 MiB | 1,189 and 1,335 MiB | 1.07 and 1.09 |
| gemma-4-E2B | none, 3 | 1,699 and 1,841 MiB | 1,663 and 1,785 MiB | 0.95 and 1.06 |

### Group 6: whether the reply changes

| model | prompt tokens | tokens written, 16-bit and 8-bit | identical leading tokens, two 16-bit launches | identical leading tokens, 16-bit and 8-bit | same token at the same place, 16-bit and 8-bit |
| --- | --- | --- | --- | --- | --- |
| gemma-4-12B | 4,028 | 119 and 119 | 119 | 5 | 111 |
| Qwen3.5-9B | 4,027 | 162 and 161 | 162 | 154 | 155 |
| Qwen3.8-27B, Q4 | 4,027 | 145 and 145 | 145 | 51 | 64 |

Two 16-bit launches write the same reply token for token, so a difference between the types is the
cache's. Every reply ends on its own (`finish_reason` is `stop`), none is empty and none repeats
itself. Each 8-bit reply summarises the same two records in the same sentences as its 16-bit reply
and differs in wording only: gemma-4-12B writes "Architectural" for "Architecture" at its sixth
token and words its last clause differently, both clauses describing a rule the prompt contains;
Qwen3.5-9B changes its last five words; Qwen3.8-27B rewords three phrases. No reply fails the
check. One prompt per model shows whether the reply moves, not whether it is worse.

## The rule applied

| tier | model | 1 accepted | 2 gain | 3 rate | 4 output | result |
| --- | --- | --- | --- | --- | --- | --- |
| subagent | gemma-4-E4B | yes with `auto`, no with off | no: 18 to 43 MiB at 8K | no: 0.67 and 0.74 at 64K | not drawn | does not meet it |
| chat | gemma-4-12B | yes | yes: one step | no: 0.66 to 0.76 | passes | does not meet it |
| chat | Qwen3.5-9B | yes | yes: one step | no: 0.87 at 192K, 0.67 at draft length 3 | passes | does not meet it |
| deep | Qwen3.8-27B, Q4 file | yes, with `auto` too | yes: 24K to 48K, and 446 to 734 MiB at 16K and 24K | yes: 0.97 and 1.00 without drafting, 0.97 and 1.00 at the best 8-bit lengths | passes | meets it |
| deep | Qwen3.8-27B, NVFP4 file | yes | yes: 32K to 48K | no: 0.81 at 32K and draft length 1 | not drawn for this file | does not meet it |
| subagent | the four small models | yes | no: 7 to 94 MiB at 8K | yes at 8K | not drawn | do not meet it |

The chat and NVFP4 rows ran with flash attention on, the model card's setting; `auto` was read
for gemma-4-E4B and the Q4 file only. The deep tier meets the rule on the Qwen3.8-27B Q4
file, by a small margin at 16K, where draft lengths 4 and 5 read 0.84 and 0.88. The NVFP4
file does not meet condition 3. No default was changed (ADR-0077 decision 8).

## Ratios across two nights

[The rows of 2026-11-19](kv-cache-every-model.md) form each ratio inside one night and apply the
rule again. The chat, Q4 and group 5 ratios above divide an 8-bit row of 2026-11-18 by a 16-bit
row of an earlier night, and a launch drawn again on 2026-11-19 reads 1.06 to 1.23 times its
earlier rate. So they overstate the 8-bit cache by the factor between their nights, about 1.05
to 1.07 for the Q4 file. The gemma-4-E4B and NVFP4 ratios are of one night.
