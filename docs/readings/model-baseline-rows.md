# Readings: the rows of the model baseline of 2026-11-16

One table per model and tier of [the model baseline](model-baseline.md), which has the method,
the files and what the run found. Every row is drawn with the context in the default 16-bit
cache. Memory is in MiB at the highest reading of a row, with the process memory beside it for a
model split with RAM or on the CPU.

- **No draft** is the row's rate over the rate of the anchor row: gemma-4-12B at 64K, no draft,
  drawn on 2026-11-16, the first row of its table below.
- **Prompt pass** is the row's prompt pass over the anchor's.
- **1 to 6** are the draft lengths, each over the no-draft rate of the same row. The fastest
  length is in bold where it is faster than no draft, and "best" repeats it. "over" is a length
  that goes over the budget, and an empty cell was not drawn.
- **Drawn** is the date of the no-draft row, then each draft length drawn on another date. The
  sentence under a table names the contexts whose no-draft and prompt pass figures divide a row
  of another date by the anchor. A table without that sentence is of the anchor's date.

Method: `python3 tools/repo-tables.py first-rows` under
`measurements/model-baseline-2026-11-16/`, which git ignores, prints every table below from
`bench/baseline.jsonl`; `baseline.md` there has the same rows with their absolute rates.

## Subagent models, alone on the card

### gemma-4-E4B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-16 | 3,172 MiB | 3,376 MiB | 2.65 | 1.95 | 1.40 | **1.55** | 1.53 | 1.45 |  |  | 2, 1.55 |
| 8K | 2026-11-16 | 3,351 MiB | 3,579 MiB | 3.51 | 1.82 | 1.42 | 1.55 | **1.60** | 1.52 | 1.36 |  | 3, 1.60 |
| 16K | 2026-11-16 | 3,689 MiB | 4,020 MiB | 3.79 | 1.69 | 1.40 | **1.51** | 1.44 | 1.47 | 1.35 | 1.30 | 2, 1.51 |
| 32K | 2026-11-16 | 4,353 MiB | 4,827 MiB | 3.46 | 1.44 | 1.41 | **1.59** | 1.53 | 1.47 |  |  | 2, 1.59 |
| 64K | 2026-11-16 | 5,764 MiB | 6,501 MiB | 2.65 | 1.04 | 1.35 | **1.60** | 1.55 | 1.48 |  |  | 2, 1.60 |
| 128K | 2026-11-16 | 8,512 MiB | 9,930 MiB | 1.67 | 0.48 | 1.73 | **1.85** | 1.78 | 1.83 | 1.84 | 1.67 | 2, 1.85 |

### gemma-4-E2B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-16 | 1,618 MiB | 1,867 MiB | 10.66 | 3.14 | 1.24 | 1.31 | **1.35** | 1.21 | 1.17 |  | 3, 1.35 |
| 8K | 2026-11-16 | 1,699 MiB | 1,841 MiB | 11.53 | 2.96 | 1.26 | 1.47 | **1.51** | 1.43 | 1.38 |  | 3, 1.51 |
| 16K | 2026-11-16 | 1,680 MiB | 1,875 MiB | 11.75 | 2.87 | 1.26 | 1.36 | **1.42** | 1.34 | 1.17 |  | 3, 1.42 |
| 32K | 2026-11-16 | 1,862 MiB | 2,026 MiB | 10.02 | 2.61 | 1.24 | 1.41 | **1.45** | 1.29 | 1.15 |  | 3, 1.45 |
| 64K | 2026-11-16 | 2,064 MiB | 2,327 MiB | 7.09 | 2.30 | 1.20 | **1.29** | 1.20 | 1.24 | 1.18 | 1.06 | 2, 1.29 |
| 128K | 2026-11-16 | 2,558 MiB | 2,835 MiB | 4.51 | 1.83 | 1.13 | **1.17** | 1.05 | 1.05 |  |  | 2, 1.17 |

### Qwen3.5-4B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-17 | 3,217 MiB | 3,667 MiB | 2.75 | 1.93 | 1.05 | 1.11 | **1.39** | 1.24 | 1.20 |  | 3, 1.39 |
| 8K | 2026-11-17 | 3,349 MiB | 3,819 MiB | 3.23 | 1.90 | 1.00 | 1.08 | **1.37** | 1.26 | 1.24 |  | 3, 1.37 |
| 16K | 2026-11-17 | 3,615 MiB | 4,123 MiB | 3.18 | 1.80 | 1.08 | 1.15 | **1.30** | 1.24 | 1.18 |  | 3, 1.30 |
| 32K | 2026-11-17 | 4,146 MiB | 4,782 MiB | 2.54 | 1.67 | 1.09 | 1.16 | 1.33 | **1.38** | 1.30 | 1.26 | 4, 1.38 |
| 64K | 2026-11-17 | 5,199 MiB | 5,982 MiB | 2.15 | 1.39 | 1.15 | 1.28 | 1.42 | **1.50** | 1.46 | 1.32 | 4, 1.50 |
| 128K | 2026-11-17 | 7,318 MiB | 8,367 MiB | 1.50 | 1.08 | 1.20 | 1.29 | **1.48** | 1.43 | 1.37 |  | 3, 1.48 |
| 256K | 2026-11-17 | 11,543 MiB | 13,223 MiB | 0.92 | 0.70 | 1.30 | 1.52 | **1.53** | 1.43 | 1.33 |  | 3, 1.53 |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.5-2B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-17 | 1,683 MiB | 1,965 MiB | 6.20 | 3.33 | 0.86 | 0.90 | 0.91 | 0.82 | 0.73 |  | no draft |
| 8K | 2026-11-17 | 1,735 MiB | 1,973 MiB | 7.04 | 3.20 | 0.91 | 0.86 | 0.92 | 0.86 | 0.80 |  | no draft |
| 16K | 2026-11-17 | 1,837 MiB | 2,089 MiB | 7.43 | 3.00 | 0.91 | 0.91 | 0.95 | 0.88 | 0.81 |  | no draft |
| 32K | 2026-11-17 | 2,056 MiB | 2,335 MiB | 6.88 | 2.87 | 0.89 | 0.89 | 0.92 | 0.91 | 0.87 |  | no draft |
| 64K | 2026-11-17 | 2,463 MiB | 2,847 MiB | 5.69 | 2.54 | 0.85 | 0.78 | 0.82 | 0.71 | 0.66 |  | no draft |
| 128K | 2026-11-17 | 3,295 MiB | 3,867 MiB | 4.22 | 2.01 | 0.91 | 0.93 | 0.90 | 0.82 |  |  | no draft |
| 256K | 2026-11-17 | 4,967 MiB | 5,883 MiB | 2.81 | 1.51 | 0.94 | 0.92 | 0.89 |  |  |  | no draft |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.5-0.8B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-17 | 1,165 MiB | 1,319 MiB | 8.32 | 4.00 | 0.83 | 0.83 | 0.80 |  |  |  | no draft |
| 8K | 2026-11-17 | 1,217 MiB | 1,391 MiB | 8.82 | 3.89 | 0.85 | 0.86 | 0.81 | 0.70 |  |  | no draft |
| 16K | 2026-11-17 | 1,323 MiB | 1,499 MiB | 8.04 | 3.65 | 0.83 | 0.82 | 0.77 |  |  |  | no draft |
| 32K | 2026-11-17 | 1,531 MiB | 1,755 MiB | 8.54 | 3.31 | 0.87 | 0.84 | 0.79 |  |  |  | no draft |
| 64K | 2026-11-17 | 1,947 MiB | 2,287 MiB | 7.73 | 2.87 | 0.89 | 0.93 | 0.88 | 0.81 |  |  | no draft |
| 128K | 2026-11-17 | 2,779 MiB | 3,293 MiB | 5.31 | 2.32 | 0.84 | 0.79 | 0.74 |  |  |  | no draft |
| 256K | 2026-11-17 | 4,483 MiB | 5,345 MiB | 3.25 | 1.64 | 0.83 | 0.83 | 0.73 |  |  |  | no draft |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

## Chat models, with room kept for one E4B server

### gemma-4-12B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64K | 2026-11-16; lengths 3, 4 and 5 of 2026-11-17 | 8,381 MiB | 9,012 MiB | 1.00 | 1.00 | 1.40 | 1.55 | **1.72** | 1.63 | 1.53 |  | 3, 1.72 |
| 128K | 2026-11-17; length 1 of 2026-11-16 | 9,531 MiB | 10,372 MiB | 0.70 | 0.94 | 1.34 | 1.51 | **1.55** | 1.51 | 1.39 |  | 3, 1.55 |
| 192K | 2026-11-17 | 10,583 MiB | 11,263 MiB | 0.53 | 0.83 | 1.31 | **1.39** | 1.33 | 1.09 |  |  | 2, 1.39 |
| 256K | 2026-11-17 | 11,786 MiB | 12,424 MiB | 0.45 | 0.78 | **1.28** | 1.26 | 1.22 |  |  |  | 1, 1.28 |

At 128K, 192K and 256K the no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor
of 2026-11-16.

### Qwen3.5-9B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64K | 2026-11-17 | 7,498 MiB | 8,367 MiB | 1.61 | 1.10 | 1.22 | 1.28 | 1.44 | **1.46** | 1.38 | 1.29 | 4, 1.46 |
| 128K | 2026-11-17 | 9,587 MiB | 10,753 MiB | 1.18 | 0.87 | 1.28 | 1.33 | **1.56** | 1.52 | 1.43 |  | 3, 1.56 |
| 160K | 2026-11-17 | 10,670 MiB |  | 1.05 | 0.79 |  |  |  |  |  |  |  |
| 192K | 2026-11-17 | 11,727 MiB | 13,191 MiB | 0.95 | 0.73 | 1.29 | 1.41 | **1.57** | 1.37 | 1.36 |  | 3, 1.57 |
| 256K | 2026-11-17 | 13,841 MiB |  | 0.78 | 0.60 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

## Chat models, with room kept for two E4B servers

### gemma-4-12B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 160K | 2026-11-17 | 10,025 MiB | 10,761 MiB | 0.61 | 0.91 | 1.35 | 1.48 | **1.55** | 1.31 | 1.22 |  | 3, 1.55 |
| 192K | 2026-11-17 | 10,565 MiB |  | 0.53 | 0.83 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.5-9B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 128K | 2026-11-17 | 9,611 MiB | 10,755 MiB | 1.16 | 0.84 | 1.27 | 1.32 | **1.58** | 1.53 | 1.40 |  | 3, 1.58 |
| 160K | 2026-11-17 | 10,667 MiB |  | 1.03 | 0.77 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

## Deep models, alone on the card

### Qwen3.8-27B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-17 | 16,409 MiB | 17,915 MiB | 0.60 | 0.51 | 1.26 | 1.49 | 1.76 | 1.82 | **1.88** | 1.72 | 5, 1.88 |
| 20K | 2026-11-17 | 16,673 MiB | 18,053 MiB | 0.59 | 0.51 | 1.25 | 1.68 | 1.79 | 1.80 | **1.84** | over | 5, 1.84 |
| 24K | 2026-11-17 | 16,931 MiB | 18,023 MiB | 0.62 | 0.50 | 1.30 | 1.55 | **1.75** | over |  |  | 3, 1.75 |
| 40K | 2026-11-17 | 17,973 MiB |  | 0.52 | 0.48 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### gemma-4-31B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-17 | 17,727 MiB + 4.0 GiB RAM | 17,745 MiB + 3.3 GiB RAM | 0.29 | 0.15 | **1.24** | 1.13 | 1.17 | 1.05 | 0.99 |  | 1, 1.24 |
| 32K | 2026-11-17 | 17,887 MiB + 4.2 GiB RAM | 17,765 MiB + 3.8 GiB RAM | 0.27 | 0.10 | 0.85 | 0.73 | 0.72 |  |  |  | no draft |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### gemma-4-26B-A4B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 256K | 2026-11-17 | 17,886 MiB + 1.9 GiB RAM | 17,801 MiB + 2.0 GiB RAM | 0.47 | 0.73 | **1.04** | 1.03 | 0.95 |  |  |  | 1, 1.04 |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.6-35B-A3B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 256K | 2026-11-17 | 17,941 MiB + 1.2 GiB RAM | 18,076 MiB + 1.6 GiB RAM | 0.41 | 0.69 | 1.05 | **1.12** | over | over |  |  | 2, 1.12 |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.8-Flash-Next, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32K | 2026-11-17; lengths 2 and 3 of 2026-11-18 | 17,531 MiB + 2.4 GiB RAM | 17,581 MiB + 9.7 GiB RAM | 0.04 | 0.33 | 0.99 | 0.93 | 0.85 |  |  |  | no draft |
| 256K (short prompts only) | 2026-11-17 | 17,991 MiB + 2.3 GiB RAM | 17,786 MiB + 7.8 GiB RAM |  | 0.25 | 0.84 | 0.74 | 0.78 | 0.80 | 0.72 | 0.67 | no draft |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

## Models on the CPU

### gemma-4-E4B, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-17 | 3.1 GiB RAM | 3.2 GiB RAM | 0.03 | 0.15 | 0.99 | 0.92 | **1.09** | 0.87 | 0.72 |  | 3, 1.09 |
| 16K (short prompts only) | 2026-11-17 | 3.1 GiB RAM |  |  | 0.14 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.5-2B, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-17 | 0.9 GiB RAM | 1.1 GiB RAM | 0.05 | 0.24 | 0.80 | 0.66 | 0.56 |  |  |  | no draft |
| 16K | 2026-11-17 | 1.0 GiB RAM | 1.2 GiB RAM | 0.05 | 0.17 | 0.72 | 0.58 | 0.46 |  |  |  | no draft |
| 32K (short prompts only) | 2026-11-17 | 1.2 GiB RAM |  |  | 0.24 |  |  |  |  |  |  |  |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.

### Qwen3.5-0.8B, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, over the anchor's | no draft, over the anchor | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-17 | 0.4 GiB RAM | 0.5 GiB RAM | 0.10 | 0.33 | 0.77 | 0.58 | 0.53 |  |  |  | no draft |
| 16K | 2026-11-17 | 0.4 GiB RAM | 0.6 GiB RAM | 0.08 | 0.22 | 0.67 | 0.51 | 0.41 |  |  |  | no draft |
| 32K | 2026-11-17 | 0.7 GiB RAM | 1.0 GiB RAM | 0.06 | 0.12 | 0.72 | 0.53 | 0.41 |  |  |  | no draft |

The no-draft and prompt pass columns divide a row of 2026-11-17 by the anchor of 2026-11-16.
