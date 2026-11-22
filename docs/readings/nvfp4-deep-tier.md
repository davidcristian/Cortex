# Readings: the NVFP4 files for the deep tier

Memory and rate rows for the two NVFP4 files the models mount holds, beside the rows
[the model baseline of 2026-11-16](model-baseline.md) drew for the same two models in their Q4
files. NVFP4 is a 4-bit floating point weight format.
[R-1244](../refinements/tasks/1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md)
proposes a choice of file on these rows, and
[R-1245](../refinements/tasks/1245-the-nvfp4-files-have-none-of-the-rows-the-deep-pick-is-compared-on.md)
names the rows they do not have. Memory is `nvidia-smi` `memory.used` at the highest reading of a
row, less what the card held before the load, and stays absolute because a reader compares it with
their own card. A rate describes only the card it was read on, so each one is written as a ratio of
another row's rate.

| name here | file under the models mount | size |
| --- | --- | --- |
| Qwen NVFP4 | `esatapedico/Qwen3.8-27B-NVFP4-MTP-GGUF/Qwen3.8-27B-NVFP4-MTP-MID-HIGH.gguf` | 16.91 GB |
| Qwen Q4 | `unsloth/Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-Q4_K_M.gguf` | 16.56 GB |
| gemma NVFP4 | `esatapedico/Gemma-4-31B-IT-NVFP4-GGUF/Gemma-4-31B-IT-NVFP4-MID-HIGH.gguf` | 17.99 GB |
| gemma Q4 | `unsloth/gemma-4-31B-it-qat-GGUF/gemma-4-31B-it-qat-UD-Q4_K_XL.gguf` | 17.29 GB |

## How the rows were drawn

**2026-11-18** for the NVFP4 rows and 2026-11-16 to 2026-11-17 for the Q4 rows, all on
`llama-server` build b12375 from the `cortex-model-host` image. One server at a time on the 24 GB
card (24,463 MiB), started with `--parallel 1 --jinja --cache-ram 0 -fa on`, the sampler of the
model's card, and no `--cache-type-k` or `--cache-type-v`, so the context is held in the default
16-bit cache. A model held whole on the card runs with `-ngl 99 --fit off`. A model that does not
fit whole runs with `--fit on` and 8 threads, which keeps the layers that fit on the card and the
rest in RAM.

- **Budget.** Models get 18,177 MiB at the highest reading of a row: the card less 4,750 MiB counted
  for the desktop's apps and 1,536 MiB kept free.
- **Rate.** Read while 256 tokens are written after a prompt that fills the context less 512
  tokens, as the median of three seeds. The prompt pass is the rate at which that prompt is read.
- **Draft lengths.** None, then 1 to 6. A ladder stops when the rate falls twice in a row or a
  length goes over the budget.
- **Largest context.** Searched from the top over powers of two and sums of a power of two with one
  of the next two lower powers (16K, 20K, 24K, 32K, 40K, 48K).
- **Power.** A row of a model held whole is kept when `enforced.power.limit` over
  `power.max_limit` has a median of 0.84 or more across the row, the rule the baseline keeps a row
  on. Two NVFP4 cells named below did not reach it. A split run loads the CPU and the limit falls:
  the split rows of both gemma files were drawn at 0.80 to 0.87.

Method: `tools/bench3.py --phase deep --out nvfp4.jsonl` under
`measurements/model-baseline-2026-11-16/`, which git ignores. The NVFP4 rows are in
`bench/nvfp4.jsonl` there, the Q4 rows in `bench/baseline.jsonl` and in
[the baseline's rows](model-baseline-rows.md), and `nvfp4.md` has both sets with their absolute
rates.

## Whether the engine loads the files

Both files load on build b12375 and answer a short question correctly. Each header gives tensor
type 40 to the weights of the model's own blocks, which the loader prints as `nvfp4`.

| | Qwen NVFP4 | gemma NVFP4 |
| --- | --- | --- |
| tensors of type `nvfp4` | 448, 12.75 GiB | 410, 15.34 GiB |
| tensors of type `q8_0` | 10, 2.94 GiB: the output layer, the token embedding and the draft block | 1, 1.39 GiB: the token embedding |
| loader lines | `file type   = Q8_0`, `file size   = 15.74 GiB (4.95 BPW)` | `file type   = Q8_0`, `file size   = 16.74 GiB (4.68 BPW)` |
| draft layer | in the file, as in the Q4 file: `qwen35.nextn_predict_layers = 1` | none in the file or its folder |

With every layer of the Qwen file on the card the engine logs `offloaded 66/66 layers to GPU`,
`CUDA0 model buffer size = 14830.16 MiB` and `CPU_Mapped model buffer size =  1288.28 MiB`. The two
buffers add up to the 15.74 GiB of tensors in the file, so the weights are held on the card in
their 4-bit form. The log has no line about converting the format, and it does not say how the
card multiplies the type. The two other engine builds present on the machine (b12169 and b10680)
contain the type's name in their libraries and were not run.

The Qwen file drafts with `--spec-type draft-mtp` alone (`creating MTP draft context against the
target model`). The gemma file has no drafter of its own. The engine accepts the Q4 file's drafter,
`unsloth/gemma-4-31B-it-qat-GGUF/mtp-gemma-4-31B-it-Q8_0.gguf`, beside it and drafts with it.

## Qwen3.8-27B: held whole on the card

The engine's own projection for the NVFP4 file is 15,019 MiB at a 4K context and 15,799 MiB at 16K,
302 MiB under the Q4 file's at both. The NVFP4 file is larger on disk, and the engine keeps 1,288
MiB of it, the `q8_0` token embedding, in RAM.

| | Qwen NVFP4 | Qwen Q4 |
| --- | --- | --- |
| largest context with the draft layer | 32K, draft length 1 only (18,104 MiB; 2 reads 18,258 MiB, over) | 24K, draft lengths 1 to 3 (18,023 MiB at 3; 4 reads 18,249 MiB, over) |
| largest context without drafting | 40K, 17,709 MiB (48K reads 18,229 MiB, over) | 40K, 17,973 MiB |

Without drafting, and at the best draft length that fits:

| context | NVFP4 memory, no draft | Q4 memory, no draft | NVFP4 rate over Q4 rate, no draft | prompt pass, NVFP4 over Q4 | NVFP4 best draft length | Q4 best draft length | NVFP4 best rate over Q4 best rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 16,164 MiB | 16,409 MiB | 1.12 | 1.96 | 4, 17,431 MiB | 5, 17,766 MiB | 0.94 |
| 20K | 16,413 MiB | 16,673 MiB | 1.11 | 1.94 | 2, 17,428 MiB | 5, 18,053 MiB | 0.92 |
| 24K | 16,665 MiB | 16,931 MiB | 1.11 | 1.80 | 2, 17,699 MiB | 3, 18,023 MiB | 0.96 |
| 32K | 17,189 MiB | not drawn | | | 1, 18,104 MiB | no length fits | |
| 40K | 17,709 MiB | 17,973 MiB | 1.10 | 1.78 | no length fits | no length fits | |

Each draft length as a ratio of the same file's no-draft rate at that context:

| context | file | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | NVFP4 | 1.41 | 1.55 | 1.50 | 1.58 | 1.43 | 1.33 |
| 16K | Q4 | 1.26 | 1.49 | 1.76 | 1.82 | 1.88 | 1.72 |
| 20K | NVFP4 | 1.35 | 1.52 | 1.46 | 1.48 | 1.37 | 1.28 |
| 20K | Q4 | 1.25 | 1.68 | 1.79 | 1.80 | 1.84 | over |
| 24K | NVFP4 | 1.34 | 1.52 | 1.45 | 1.44 | | |
| 24K | Q4 | 1.30 | 1.55 | 1.75 | over | | |
| 32K | NVFP4 | 1.43 | over | | | | |

The NVFP4 file gains more than the Q4 file at draft length 1 and less at every length from 3 up.
The share of drafted tokens accepted is within 0.04 of the Q4 file's at every length and context
(0.71 to 0.74 at 1, 0.31 to 0.33 at 6), so the smaller gain does not come from fewer accepted
tokens. Its ladders at 16K, 20K and 24K were drawn after the search, so that each has a Q4 row at
the same context beside it. Two NVFP4 cells, 16K at draft 3 and 4, were drawn four times each and
never under the power rule: the kept rows are at 0.82 and 0.83, and the four draws of each agree
within 0.05 of the no-draft rate.

### Both files on one night

Every ratio above divides an NVFP4 row of 2026-11-18 by a Q4 row of 2026-11-16 or 2026-11-17,
and the same launch reads a different rate on another night
([the cache type rows of every model](kv-cache-every-model.md)). On **2026-11-19** both files
were drawn at 20K with the 16-bit cache, without drafting and at one draft length each, the
fastest of the file's 8-bit ladder: 2 for the NVFP4 file and 4 for the Q4 file.

| at 20K | the rows above, of two nights | both rows of 2026-11-19 |
| --- | --- | --- |
| NVFP4 rate over Q4 rate, no draft | 1.11 | 1.05 |
| prompt pass, NVFP4 over Q4 | 1.94 | 1.80 |
| NVFP4 at draft length 2 over the Q4 file's fastest length | 0.92, the Q4 file at 5 | 0.91, the Q4 file at 4 |
| NVFP4 memory under Q4 memory, no draft | 260 MiB | 249 MiB |

With an 8-bit cache on the same night the two rate ratios are 1.05 and 0.91 again, and the NVFP4
file takes 300 MiB less. The ratios at 16K, 24K and 40K divide the same two nights and were not
drawn again. Method: `q8-probes/ref.py Qwen3.8-27B 20480 deep 0` and the same for
`Qwen3.8-27B-NVFP4` under `measurements/model-baseline-2026-11-16/`, rows in `bench/q8-ref.jsonl`.

## gemma-4-31B: split with RAM

Neither gemma file fits whole at any context. The engine projects 18,921 MiB for the NVFP4 file at
a 4K context and 19,893 MiB at 16K, 756 MiB over the Q4 file's projection at both and over the
budget before any context is added. One load of the NVFP4 file with every layer on the card at 8K
took 19,530 MiB.

Most of the 756 MiB is the token embedding, which gemma also uses as its output layer and which
the engine holds once in RAM and once on the card. In the engine's memory breakdown the card and
RAM model buffers of the NVFP4 file add up to about 1,430 MiB more than the file's tensors, and the
file's `q8_0` embedding is 1,428 MiB. For the Q4 file the same sum is about 760 MiB over, and its
4-bit embedding is 756 MiB.

Split with RAM under the same budget, the NVFP4 file has two layers fewer on the card than the Q4
file at each context:

| | gemma NVFP4 | gemma Q4 |
| --- | --- | --- |
| layers on the card at 16K, without and with the drafter | 53 and 51 | 55 and 53 |
| layers on the card at 32K, without and with the drafter | 49 and 47 | 51 and 49 |
| memory at 16K, no draft | 17,866 MiB and 4.0 GiB of RAM | 17,727 MiB and 4.0 GiB of RAM |
| memory at 32K, no draft | 17,736 MiB and 4.5 GiB of RAM | 17,887 MiB and 4.2 GiB of RAM |
| best draft length at 16K | none | 1, at 1.24 of its no-draft rate |
| best draft length at 32K | none | none |

| context | draft | NVFP4 rate over Q4 rate | NVFP4 over its no-draft rate | Q4 over its no-draft rate | drafted tokens accepted, NVFP4 | drafted tokens accepted, Q4 |
| --- | --- | --- | --- | --- | --- | --- |
| 16K | none | 0.87 | 1 | 1 | | |
| 16K | 1 | 0.69 | 0.98 | 1.24 | 0.69 | 0.85 |
| 16K | 2 | 0.74 | 0.96 | 1.13 | 0.59 | 0.77 |
| 16K | 3 | 0.66 | 0.89 | 1.17 | 0.51 | 0.70 |
| 32K | none | 0.68 | 1 | 1 | | |
| 32K | 1 | 0.79 | 0.99 | 0.85 | 0.71 | 0.84 |
| 32K | 2 | 0.81 | 0.88 | 0.73 | 0.57 | 0.76 |
| 32K | 3 | 0.74 | 0.78 | 0.72 | 0.49 | 0.68 |

Each NVFP4 ladder stopped at draft 3, its second fall in a row; the Q4 ladder at 16K went on to
1.05 and 0.99 at draft 4 and 5. The prompt pass of the NVFP4 file is 1.46 of the Q4 file's at 16K
and 1.21 at 32K without drafting. The drafter file comes from the Q4 file's folder: it drafts
beside the NVFP4 file, and fewer of its tokens are accepted there at every length. The NVFP4 row
at 16K without drafting had the lower power limit of the two (0.82 against 0.87 or more), so part
of its 0.87 may be the limit; the two rows at 32K had nearly the same limit (0.84 and 0.85).

These ratios divide NVFP4 rows of 2026-11-18 by Q4 rows of 2026-11-17. The Q4 file's 16-bit split
rows were drawn again on 2026-11-19 and read 1.01 to 1.07 times its rows of 2026-11-17. The NVFP4
file was not drawn again, so it has no ratio of one night.

## What these rows do not say

- Nothing about what the gemma NVFP4 file writes. No stop row, reasoning count or injection row
  exists for it (R-1245). The Qwen NVFP4 file's rows are in
  [what the Qwen NVFP4 file writes](nvfp4-deep-counts.md).
- Nothing about a deployment that gives the deep tier more of the card than 18,177 MiB.
- Nothing about an 8-bit context cache, which has its own record:
  [the cache type rows of every model](kv-cache-every-model.md).
