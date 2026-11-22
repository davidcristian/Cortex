# Draft length 2 against 3 on the Qwen NVFP4 file has six texts

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-22

The deep tier drafts at length 3 for whichever file a deployment names
(`DEFAULT_BRAIN_DRAFT_LENGTH`). On 2026-11-22 the Qwen NVFP4 file at 16384 and `q8_0` read
1.049 of its length 3 rate at length 2 on three texts, and 1.049 by the median and 1.039 by
the mean on three other texts
([readings](../../readings/nvfp4-deep-pair.md#qwen38-27b-at-16k-held-whole-on-the-card)). The
Q4 file read 0.90 on the first three texts and 0.966 by the median on the others.

The six texts do not say whether length 2 is faster:

- Text by text they read 1.019 to 1.177, each one faster at length 2, with a mean of 1.067.
- Three of the six are the texts length 2 was picked on, as the fastest of six lengths.
- Each length is one launch, and two launches of one cell sit up to 0.018 apart.
- The record's standard error of about 0.04 takes the spread of twelve texts for each length,
  as if the two lengths wrote other texts. The six texts are the same at both lengths, so that
  figure is wider than the rows.

[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md) compares
the two files at length 3, where the NVFP4 file writes 0.943 of the Q4 file's rate by the mean
of twelve texts. A length that is faster for the NVFP4 file would change that comparison and
would be part of what its choice B changes.

What would close it: a rule written before the rows, text by text over the twelve ratios of a
cell, then both Qwen files at lengths 2 and 3 on twelve texts other than seeds 7 to 9, two
launches a cell, the cells in turn, started by the model host as the tier ships. The reading
goes into the record, and the default changes only when the rule written first calls for it.

## History

- 2026-11-22: filed from the draft ladders of both Qwen files at 16K, which R-1244 compares
  the two files on.
