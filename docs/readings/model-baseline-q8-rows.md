# Readings: the rows of the model baseline at an 8-bit KV cache

One table per model and tier of [the 8-bit baseline](model-baseline-q8.md), which has the method
and the units. Every table is of 8-bit rows but the first, which has the 16-bit rows of
gemma-4-E4B with flash attention on. Memory is in MiB at the highest reading of a row.

- **No draft** and **prompt pass** are the 8-bit row over the 16-bit row of the same launch and
  date, and empty where that date has no 16-bit row. In the first table they are over the anchor
  launch of the same date.
- **1 to 6** are the draft lengths, each over the 8-bit no-draft rate of the same row. The
  fastest length is in bold where it is faster than no draft. "over" is a length that goes over
  the budget, and an empty cell was not drawn.
- **Drawn** is the date of the no-draft row, then each draft length drawn on another date.

Method: `python3 tools/repo-tables.py q8-rows-small q8-rows-deep` under
`measurements/model-baseline-2026-11-16/`, which git ignores.

## Subagent models, alone on the card

### gemma-4-E4B, flash attention on, 16-bit rows, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 3,011 MiB | 3,121 MiB | 5.10 | 2.09 | 1.36 | **1.58** | 1.55 | 1.51 |  |  | 2, 1.58 |
| 8K | 2026-11-18; lengths 1, 2, 3 and 4 of 2026-11-19 | 3,072 MiB | 3,201 MiB |  |  | 1.46 | **1.63** | 1.61 | 1.53 |  |  | 2, 1.63 |
| 16K | 2026-11-19 | 3,215 MiB | 3,337 MiB | 5.32 | 1.89 | 1.38 | 1.49 | **1.49** | 1.44 | 1.37 |  | 3, 1.49 |
| 32K | 2026-11-19 | 3,487 MiB | 3,629 MiB | 4.66 | 1.72 | 1.35 | 1.51 | **1.55** | 1.42 | 1.35 |  | 3, 1.55 |
| 64K | 2026-11-18; lengths 1, 2, 3 and 4 of 2026-11-19 | 4,041 MiB | 4,203 MiB |  |  | 1.44 | **1.52** | 1.51 | 1.48 |  |  | 2, 1.52 |
| 128K | 2026-11-19 | 5,123 MiB | 5,357 MiB | 2.62 | 1.17 | 1.24 | 1.33 | 1.19 | **1.43** | 1.36 | 1.32 | 4, 1.43 |

No 16-bit row of the same date: 8K and 64K.

### gemma-4-E4B, flash attention on, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 2,995 MiB | 3,118 MiB | 1.01 | 0.91 | 1.37 | 1.60 | 1.64 | **1.65** | 1.49 | 1.43 | 4, 1.65 |
| 8K | 2026-11-18; lengths 1, 2, 4, 5 and 6 of 2026-11-19 | 3,029 MiB | 3,175 MiB | 0.95 | 0.93 | 1.42 | **1.70** | 1.55 | 1.66 | 1.58 | 1.54 | 2, 1.70 |
| 16K | 2026-11-19 | 3,143 MiB | 3,327 MiB | 0.97 | 0.87 | 1.35 | 1.62 | **1.64** | 1.52 | 1.42 |  | 3, 1.64 |
| 32K | 2026-11-19 | 3,357 MiB | 3,623 MiB | 0.96 | 0.81 | 1.32 | 1.60 | **1.67** | 1.64 | 1.52 |  | 3, 1.67 |
| 64K | 2026-11-18; lengths 1, 3, 4 and 5 of 2026-11-19 | 3,790 MiB | 4,215 MiB | 0.96 | 0.67 | 1.44 | 1.58 | **1.75** | 1.51 | 1.44 |  | 3, 1.75 |
| 128K | 2026-11-19 | 4,655 MiB | 5,401 MiB | 0.95 | 0.58 | 1.34 | 1.51 | **1.51** | 1.47 | 1.49 | 1.46 | 3, 1.51 |

### Qwen3.5-4B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 3,213 MiB | 3,606 MiB |  |  | 1.06 | 1.12 | **1.43** | 1.28 | 1.25 |  | 3, 1.43 |
| 8K | 2026-11-19; length 3 of 2026-11-18 | 3,251 MiB | 3,623 MiB |  |  |  |  | **1.21** |  |  |  | 3, 1.21 |
| 16K | 2026-11-19 | 3,428 MiB | 3,954 MiB | 1.00 | 1.00 | 1.02 | 1.11 | **1.32** | 1.30 | 1.28 |  | 3, 1.32 |
| 32K | 2026-11-19 | 3,779 MiB | 4,473 MiB |  |  | 1.04 | 1.12 | 1.26 | **1.35** | 1.31 | 1.20 | 4, 1.35 |
| 64K | 2026-11-19 | 4,484 MiB | 5,406 MiB |  |  | 0.93 | 1.04 | 1.16 | **1.24** | 1.18 | 1.21 | 4, 1.24 |
| 128K | 2026-11-19 | 5,892 MiB | 7,269 MiB |  |  | 0.96 | 1.02 | 1.16 | 1.14 | **1.17** | 1.10 | 5, 1.17 |
| 256K | 2026-11-19 | 8,718 MiB | 10,956 MiB |  |  | 0.97 | 1.03 | **1.25** | 1.18 | 1.15 |  | 3, 1.25 |

No 16-bit row of the same date: 4K, 8K, 32K, 64K, 128K and 256K.

### Qwen3.5-2B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 1,660 MiB | 1,883 MiB |  |  | 0.87 | 0.85 | 0.92 | 0.87 | 0.83 |  | no draft |
| 8K | 2026-11-19; length 3 of 2026-11-18 | 1,677 MiB | 1,887 MiB |  |  |  |  | 0.84 |  |  |  | no draft |
| 16K | 2026-11-19 | 1,761 MiB | 2,027 MiB | 1.00 | 1.00 | 0.88 | 0.85 | 0.90 | 0.87 | 0.80 |  | no draft |
| 32K | 2026-11-19 | 1,911 MiB | 2,241 MiB |  |  | 0.85 | 0.76 | 0.84 | 0.67 | 0.66 |  | no draft |
| 64K | 2026-11-19 | 2,215 MiB | 2,672 MiB |  |  | 0.76 | 0.71 | 0.73 | 0.73 | 0.65 |  | no draft |
| 128K | 2026-11-19 | 2,815 MiB | 3,555 MiB |  |  | 0.81 | 0.75 | 0.78 | 0.82 | 0.75 | 0.71 | no draft |
| 256K | 2026-11-20; lengths 1, 3 and 4 of 2026-11-19 | 4,011 MiB | 5,233 MiB | 0.95 | 0.92 | 0.74 | 0.79 | 0.72 | 0.63 |  |  | no draft |

No 16-bit row of the same date: 4K, 8K, 32K, 64K and 128K.

### Qwen3.5-0.8B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 1,147 MiB | 1,309 MiB |  |  | 0.81 | 0.83 | 0.78 | 0.72 |  |  | no draft |
| 8K | 2026-11-18 | 1,189 MiB | 1,335 MiB |  |  |  | 0.87 |  |  |  |  | no draft |
| 16K | 2026-11-19 | 1,261 MiB | 1,479 MiB | 0.98 | 0.98 | 0.78 | 0.92 | 0.86 | 0.76 |  |  | no draft |
| 32K | 2026-11-19 | 1,413 MiB | 1,711 MiB |  |  | 0.95 | 0.87 | 0.88 | 0.75 | 0.73 |  | no draft |
| 64K | 2026-11-19 | 1,716 MiB | 2,104 MiB |  |  | 0.82 | 0.82 | 0.81 |  |  |  | no draft |
| 128K | 2026-11-19 | 2,313 MiB | 2,963 MiB |  |  | 0.75 | 0.65 | 0.62 |  |  |  | no draft |
| 256K | 2026-11-19 | 3,512 MiB | 4,684 MiB |  |  | 0.75 | 0.61 | 0.57 |  |  |  | no draft |

No 16-bit row of the same date: 4K, 8K, 32K, 64K, 128K and 256K.

### gemma-4-E2B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4K | 2026-11-19 | 1,667 MiB | 1,759 MiB |  |  | 1.33 | **1.48** | 1.45 | 1.43 |  |  | 2, 1.48 |
| 8K | 2026-11-18 | 1,663 MiB | 1,785 MiB |  |  |  |  | **1.68** |  |  |  | 3, 1.68 |
| 16K | 2026-11-19 | 1,739 MiB | 1,860 MiB | 0.91 | 0.83 | 1.29 | **1.45** | 1.39 | 1.39 |  |  | 2, 1.45 |
| 32K | 2026-11-19 | 1,813 MiB | 2,005 MiB |  |  | 1.25 | 1.44 | **1.47** | 1.45 | 1.36 |  | 3, 1.47 |
| 64K | 2026-11-19 | 2,009 MiB | 2,355 MiB |  |  | 1.29 | 1.33 | **1.44** | 1.24 | 1.16 |  | 3, 1.44 |
| 128K | 2026-11-19 | 2,405 MiB | 2,891 MiB |  |  | 1.23 | **1.34** | 1.23 | 1.11 |  |  | 2, 1.34 |

No 16-bit row of the same date: 4K, 8K, 32K, 64K and 128K.

## Chat models, with room kept for one E4B server

### Qwen3.5-9B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64K | 2026-11-20; lengths 1, 2, 4, 5 and 6 of 2026-11-19 | 6,753 MiB | 7,782 MiB | 0.96 | 0.96 | 1.02 | 1.06 | **1.39** | 1.25 | 1.27 | 1.11 | 3, 1.39 |
| 128K | 2026-11-20; lengths 1, 2, 4 and 5 of 2026-11-19 | 8,161 MiB | 9,600 MiB | 0.95 | 0.95 | 0.97 | 1.04 | **1.29** | 1.22 | 1.17 |  | 3, 1.29 |
| 192K | 2026-11-18 |  | 11,355 MiB |  |  |  |  | **1.20** |  |  |  | 3, 1.20 |
| 256K | 2026-11-18; lengths 2, 4, 5 and 6 of 2026-11-19 | 10,979 MiB | 13,378 MiB |  |  | 1.08 | 1.13 | 1.23 | **1.35** | 1.32 | 1.19 | 4, 1.35 |

No 16-bit row of the same date: 256K. At 192K the ladder has no no-draft row, so its draft columns
are over the no-draft row of the same launch under "Chat models, with room kept for two E4B
servers", of 2026-11-18.

### gemma-4-12B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64K | 2026-11-20; lengths 1, 3 and 4 of 2026-11-19 | 7,770 MiB | 8,454 MiB | 0.94 | 0.86 | 1.37 | **1.61** | 1.52 | 1.51 |  |  | 2, 1.61 |
| 128K | 2026-11-20; lengths 1, 2, 4 and 5 of 2026-11-19 | 8,515 MiB | 9,389 MiB | 0.97 | 0.75 | 1.38 | 1.55 | **1.70** | 1.58 | 1.51 |  | 3, 1.70 |
| 256K | 2026-11-19; lengths 1 and 2 of 2026-11-18 | 9,989 MiB | 11,551 MiB |  |  | **1.26** | 1.24 | 1.24 | 1.01 | 0.93 |  | 1, 1.26 |

No 16-bit row of the same date: 256K.

## Chat models, with room kept for two E4B servers

### gemma-4-12B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 192K | 2026-11-18 | 9,247 MiB | 10,312 MiB |  |  | 1.35 | **1.39** | 1.39 | 1.12 |  |  | 2, 1.39 |
| 256K | 2026-11-18 | 9,977 MiB |  |  |  |  |  |  |  |  |  |  |

No 16-bit row of the same date: 192K and 256K.

### Qwen3.5-9B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 160K | 2026-11-18 | 8,868 MiB | 10,521 MiB |  |  | 1.08 | 1.11 | **1.34** | 1.26 | 1.24 |  | 3, 1.34 |
| 192K | 2026-11-18 | 9,572 MiB |  |  |  |  |  |  |  |  |  |  |

No 16-bit row of the same date: 160K and 192K.
## Deep models, alone on the card

### Qwen3.8-27B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-18 | 15,963 MiB | 17,449 MiB |  |  | 1.24 | 1.58 | **1.71** | 1.53 | 1.66 | 1.62 | 3, 1.71 |
| 20K | 2026-11-19 | 16,116 MiB | 17,633 MiB | 1.02 | 0.92 | 1.23 | 1.51 | 1.75 | **1.77** | 1.68 | 1.73 | 4, 1.77 |
| 24K | 2026-11-18 | 16,267 MiB | 17,813 MiB |  |  | 1.21 | 1.59 | 1.72 | **1.76** | 1.72 | 1.60 | 4, 1.76 |
| 48K | 2026-11-19; length 1 of 2026-11-18 | 17,217 MiB | 18,173 MiB |  |  | **1.08** |  |  |  |  |  | 1, 1.08 |
| 64K | 2026-11-19 | 17,840 MiB |  |  |  |  |  |  |  |  |  |  |

No 16-bit row of the same date: 16K, 24K, 48K and 64K.

### Qwen3.8-27B-NVFP4, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-19 | 15,677 MiB | 16,957 MiB |  |  | 1.37 | **1.66** | 1.60 | 1.58 |  |  | 2, 1.66 |
| 20K | 2026-11-19 | 15,816 MiB | 17,420 MiB | 0.94 | 0.93 | 1.30 | **1.54** | 1.52 | 1.53 | 1.40 | 1.29 | 2, 1.54 |
| 24K | 2026-11-19 | 15,951 MiB | 17,444 MiB |  |  | 1.26 | 1.57 | **1.59** | 1.40 | 1.32 |  | 3, 1.59 |
| 32K | 2026-11-18 | 16,250 MiB | 17,195 MiB |  |  | **1.29** |  |  |  |  |  | 1, 1.29 |
| 48K | 2026-11-19; lengths 1 and 2 of 2026-11-18 | 16,879 MiB | 18,079 MiB |  |  | 1.21 | **1.44** | over |  |  |  | 2, 1.44 |
| 80K | 2026-11-19 | 18,123 MiB |  |  |  |  |  |  |  |  |  |  |

No 16-bit row of the same date: 16K, 24K, 32K, 48K and 80K.

### gemma-4-31B, held whole on the card

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 12K | 2026-11-19 | 18,173 MiB |  |  |  |  |  |  |  |  |  |  |

No 16-bit row of the same date: 12K.

### gemma-4-31B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-19 | 17,841 MiB + 2.3 GiB RAM | 17,765 MiB + 2.0 GiB RAM | 1.30 | 2.10 | 1.07 | 1.06 | 1.16 | 1.16 | **1.22** | 1.08 | 5, 1.22 |
| 32K | 2026-11-19 | 17,865 MiB + 2.3 GiB RAM | 17,905 MiB + 2.2 GiB RAM | 1.29 | 2.11 | 1.15 | 1.14 | **1.34** | 1.25 | 1.27 | 1.16 | 3, 1.34 |

### gemma-4-26B-A4B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32K | 2026-11-20 | 14,657 MiB + 1.2 GiB RAM | 15,297 MiB + 1.2 GiB RAM | 0.99 | 0.83 | 1.27 | **1.32** | 1.31 | 1.22 |  |  | 2, 1.32 |
| 64K | 2026-11-20 | 15,161 MiB + 1.2 GiB RAM | 15,957 MiB + 1.3 GiB RAM | 0.98 | 0.72 | 1.32 | **1.42** | 1.42 | 1.40 |  |  | 2, 1.42 |
| 256K | 2026-11-19 | 17,751 MiB + 1.5 GiB RAM | 17,875 MiB + 1.8 GiB RAM | 1.32 | 0.69 | **1.08** | 1.07 | 1.06 |  |  |  | 1, 1.08 |

### Qwen3.6-35B-A3B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 256K | 2026-11-20; length 3 of 2026-11-19 | 17,786 MiB + 1.2 GiB RAM | 17,993 MiB + 1.6 GiB RAM | 1.40 | 0.74 | 0.94 | 1.25 | **1.27** | 1.21 | 1.17 | 1.07 | 3, 1.27 |

### gemma-4-31B-NVFP4, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16K | 2026-11-20 | 17,753 MiB + 2.3 GiB RAM | 17,889 MiB + 2.1 GiB RAM | 1.30 | 1.56 | 0.99 | 1.07 | **1.07** | 1.02 | 0.98 |  | 3, 1.07 |
| 32K | 2026-11-20 | 17,712 MiB + 2.5 GiB RAM | 17,778 MiB + 2.3 GiB RAM | 1.29 | 1.94 | 1.05 | **1.13** | 1.11 | 1.05 |  |  | 2, 1.13 |

### Qwen3.8-27B, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64K | 2026-11-20 | 17,834 MiB + 1.2 GiB RAM | 17,997 MiB + 1.4 GiB RAM | 1.37 | 4.32 | 0.68 | 0.80 | 0.81 | over | over |  | no draft |

### Qwen3.8-Flash-Next, split with RAM

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 32K | 2026-11-21 | 17,805 MiB + 2.4 GiB RAM | 17,711 MiB + 5.7 GiB RAM | 0.98 | 0.94 | 1.03 | **1.16** | 1.05 | 1.03 |  |  | 2, 1.16 |
| 256K (short prompts only) | 2026-11-21 | 17,633 MiB + 2.1 GiB RAM |  |  | 1.03 |  |  |  |  |  |  |  |

## Models on the CPU

### gemma-4-E4B, flash attention on, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-20 | 2.8 GiB RAM | 3.0 GiB RAM | 0.71 | 1.05 |  |  | 0.98 |  |  |  | no draft |
| 16K (short prompts only) | 2026-11-20 | 2.9 GiB RAM |  |  | 0.99 |  |  |  |  |  |  |  |
| 32K (short prompts only) | 2026-11-20 | 3.1 GiB RAM |  |  | 0.99 |  |  |  |  |  |  |  |

### Qwen3.5-2B, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-20 | 0.9 GiB RAM | 1.0 GiB RAM | 0.75 | 1.01 | 0.87 |  |  |  |  |  | no draft |
| 16K | 2026-11-20 | 0.9 GiB RAM |  | 0.63 | 1.07 |  |  |  |  |  |  |  |
| 32K (short prompts only) | 2026-11-20 | 1.0 GiB RAM |  |  | 1.01 |  |  |  |  |  |  |  |

### Qwen3.5-0.8B, on the CPU

| context | drawn | memory, no drafter | memory, drafter | prompt pass, 8-bit over 16-bit | no draft, 8-bit over 16-bit | 1 | 2 | 3 | 4 | 5 | 6 | best |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8K | 2026-11-20 | 0.3 GiB RAM | 0.4 GiB RAM | 0.62 | 1.00 | 0.84 |  |  |  |  |  | no draft |
| 16K | 2026-11-20 | 0.4 GiB RAM |  | 0.48 | 1.12 |  |  |  |  |  |  |  |
| 32K | 2026-11-20 | 0.5 GiB RAM |  | 0.24 | 1.24 |  |  |  |  |  |  |  |
