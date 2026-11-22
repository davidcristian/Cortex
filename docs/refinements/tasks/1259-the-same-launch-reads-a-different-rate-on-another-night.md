# The same launch reads a different rate on another night

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0077](../../adr/ADR-0077-model-card-settings.md)
**Verified:** 2026-11-22

A rate row of the model baseline depends on the night it was drawn. On 2026-11-19 the same 16-bit
launch was drawn again for one cell of each model, and it read 1.06 to 1.23 times the rate of the
row the baseline drew on 2026-11-16, 2026-11-17 or 2026-11-18. For five of the eight models the
factor is larger than the 0.10 a rule in the readings allows between two settings, so a ratio of
two rows from different nights can decide a rule the wrong way. Nothing a row records explains it.
[The cache type rows of every model](../../readings/kv-cache-every-model.md) have the table of
factors and the method.

## What the rows of the two nights show

Sixteen cells held whole on the card (eight models, without drafting and at one draft length),
each row of 2026-11-19 beside the earlier row of the same launch. The rows are in
`measurements/model-baseline-2026-11-16/bench/q8-ref.jsonl`, `baseline.jsonl` and `nvfp4.jsonl`.

**What differs:**

- **The rate on a filled context**: 1.06 to 1.23 times the earlier row.
- **The rate on short prompts**, which leave the context nearly empty: 1.06 to 1.20 times.
- **The prompt pass**: 1.06 to 1.18 times for the seven models above 1B, and 1.37 and 1.51 for
  Qwen3.5-0.8B. So the whole server is faster, not only a large context.
- **The factor follows the model and the date of the earlier row**: 1.21 to 1.23 for gemma-4-E2B
  and 1.15 to 1.16 for gemma-4-12B against 2026-11-16, 1.06 to 1.15 for five models against
  2026-11-17, 1.08 to 1.09 for the NVFP4 file of Qwen3.8-27B against 2026-11-18. With and without
  drafting it agrees within 0.03 for a model, 0.05 for Qwen3.5-2B.
- **Identical 8-bit rows**: the six launches drawn without drafting on 2026-11-18 and 2026-11-19
  read 1.05 to 1.11 times their earlier row.

**What does not differ:**

- **Inside the night.** One launch drawn three times across 2026-11-19 stays within 0.975 of its
  fastest row, and four split launches drawn twice stay within 0.985.
- **The clock ratio** (`sm_ratio`): within 0.045 of the earlier row in fourteen cells, 0.083
  above it in one, and not recorded in one.
- **The draw while busy** (`power_busy`): 0.94 to 1.03 of the earlier row's.
- **The power limit**: the median ratio is 0.89 for every row of 2026-11-19. The earlier rows
  record the lowest reading, 0.80 to 0.89, and four of them a median: 0.89 for the two
  Qwen3.5-9B rows, 0.89 and 0.85 for the two NVFP4 rows.
- **The highest temperature** (`temp_max`): 2.0 degrees under to 2.5 degrees over the earlier
  row.
- **Other apps' memory before the load** (`base`): 4,114 to 4,228 MiB on 2026-11-19, 3,436 to
  4,933 MiB on the two baseline nights and 2,415 to 2,444 MiB on 2026-11-18. It does not order
  the nights by their factor.

**The split rows behave differently.** gemma-4-31B split with RAM reads 1.01 to 1.07 times its
earlier rate, under the factor of every whole cell but one, while its clock ratio at 16K rose
from 0.33 to 0.63 and its highest temperature by 4 to 14 degrees. The probe's prompt rate
(`probe_prompt_tps`, which only split rows record) reads 3.8 to 4.0 times the earlier row's for
that file and 1.10 and 1.19 for the two MoE files.

Not recorded in a row, so not compared: the revision of the driver script, the state of the host
after its restart between 2026-11-17 and 2026-11-18, and what other apps did with the card while
a row ran.

## The fixed launch on four consecutive nights

Step 1 below asks for one fixed launch on every measurement night: gemma-4-12B at 64K, 16 bits,
no draft, on build b12375. It has three rows of 2026-11-19, eight of 2026-11-20, two of
2026-11-21 and five of 2026-11-22, in `bench/q8-ref.jsonl` (`python3 q8-probes/slot3.py drift`
prints them). Each row as a ratio of the fastest row of 2026-11-19:

| night | rows | slowest | median | fastest |
| --- | --- | --- | --- | --- |
| 2026-11-19 | 3 | 0.975 | 0.980 | 1.000 |
| 2026-11-20 | 8 | 0.996 | 1.017 | 1.031 |
| 2026-11-21 | 2 | 0.991 | 0.993 | 0.995 |
| 2026-11-22 | 5 | 1.009 | 1.019 | 1.027 |

- **What it says.** The median of 2026-11-20 is 1.037 times the median of 2026-11-19, and the
  rows of the two nights overlap: the slowest row of the second night is under the fastest of
  the first. Inside 2026-11-20 the slowest row reads 0.966 of the fastest. So between these two
  nights nothing of the size of the 1.15 this cell read between 2026-11-16 and 2026-11-19 took
  place, and the difference between them is about the spread inside one night.
- **The third night is between the first two.** The two rows of 2026-11-21, the first and the
  last launch of that night's rows, read 0.979 and 0.975 of the median of 2026-11-20, and their
  median is 1.014 times the median of 2026-11-19. The last reads 0.996 of the first. Across the
  three nights every row is inside 0.975 to 1.031 of the fastest row of 2026-11-19.
- **The fourth night is beside the second.** The five rows of 2026-11-22 are the first and the
  last launch of each of two groups of rate rows and one launch inside the first group. Each
  reads 0.985 to
  1.003 of the night's first. Their median is 1.026 times the median of 2026-11-21 and 1.003
  times the median of 2026-11-20, and the night's first row reads 1.029 of the first row of
  2026-11-21. Across the four nights every row is inside 0.975 to 1.031 of the fastest row of
  2026-11-19. Every row of 2026-11-22 ran at a median power limit of 0.89 of the card's maximum,
  and the desktop's apps held 4,480 to 4,641 MiB before them.
- **What it does not say.** It names no cause. Every row of both nights ran at the highest power
  limit the card reads. On 2026-11-20 the desktop's apps held 3,993 to 4,256 MiB before the
  first four rows and 3,277 to 3,302 MiB before the last four; the first four read 0.985 to 1.00
  of the night's fastest row and the last four 0.966 to 0.989, two ranges that overlap. On
  2026-11-21 they held 4,598 and 4,567 MiB, more than before any row of the two earlier nights,
  and the rate is between theirs. Four nights do not show that a later one stays this close. A
  row still does not record the driver's revision, the display driver's version or the card's
  clock readings as absolute values, so the baseline nights cannot be compared with these three
  on those fields.

## Readings that divide rows of two nights

- [The first cache type readings](../../readings/kv-cache-types.md): the chat, Q4 and group 5
  ratios divide an 8-bit row of 2026-11-18 by a 16-bit row of an earlier night. Marked there.
- [The NVFP4 files for the deep tier](../../readings/nvfp4-deep-tier.md): every ratio of an NVFP4
  row to a Q4 row at another context than 16K. Marked there. Both pairs were drawn at 16K on
  2026-11-22, and [those rows](../../readings/nvfp4-deep-pair.md) divide one night only.
- [The cache type rows of every model](../../readings/kv-cache-every-model.md): the ratios it
  says are divided by the night factor, and the drafter's cache rows.
  [The rows of 2026-11-20](../../readings/kv-cache-remaining-cells.md) and
  [the deep tier's draw](../../readings/kv-cache-deep-whole.md) divide rows of one night only.
- [Tier drafters](../../readings/tier-drafters.md) and
  [subagent budget](../../readings/subagent-budget.md) use baseline rows of 2026-11-16 and
  2026-11-17 beside rows of 2026-11-18. Each ratio there reads as one draw; that was not checked
  row by row.
- The baseline itself spans two nights, so a ratio of a gemma row of 2026-11-16 to a Qwen row of
  2026-11-17 has the same defect. No record was searched for one.

## What to do

[The readings rules](../../readings/README.md) now say that a ratio of two rates divides two rows
of one date. That stops new ratios across nights. Left:

1. Find the cause. Keep drawing one fixed launch as the first and the last launch of every
   measurement night into `bench/q8-ref.jsonl` (the drift check's launch, gemma-4-12B at 64K
   without drafting: `python3 q8-probes/drift.py first <name>`); the four nights from 2026-11-19
   to 2026-11-22 have it. Still to build: the driver records what a row lacks, which is its own revision, the
   display driver's version and the card's clock readings as absolute values.
2. Check the two records of the fourth bullet above row by row, and search the records for a
   ratio of two baseline rows of different dates.

What would close it: the cause recorded in the readings, or every ratio in the records above
either drawn again inside one night or marked as dividing two nights.

## History

- 2026-11-19: filed when the 16-bit pairs of that night read 1.06 to 1.23 times the baseline's
  rows. The readings rule was added in the same change.
- 2026-11-20: the fixed launch of step 1 was drawn eight times across the night. Its median reads
  1.037 times the median of the three rows of 2026-11-19, and the rows of the two nights overlap.
  No cause is found: the driver records none of the three fields a row lacks. Left open for
  those fields and for step 2.
- 2026-11-21: the fixed launch was drawn as the first and the last launch of the night's rate
  rows. They read 0.979 and 0.975 of the median of 2026-11-20, and the last reads 0.996 of the
  first, so three nights in a row are inside 0.975 to 1.031 of one row. No cause is found: the
  driver still records none of the three fields a row lacks. Left open for those fields and for
  step 2.
- 2026-11-22: the fixed launch was drawn five times across the night's rate rows. Each reads
  0.985 to 1.003 of the first, their median is 1.026 times the median of 2026-11-21, and four
  nights in a row are inside 0.975 to 1.031 of one row. Both file pairs of the deep tier were
  drawn at 16K on this one night, so their ratios there no longer divide two nights. No cause is
  found: the driver still records none of the three fields a row lacks. Left open for those
  fields and for step 2.
