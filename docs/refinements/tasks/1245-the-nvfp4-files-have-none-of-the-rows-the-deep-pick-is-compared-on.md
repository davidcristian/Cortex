# The NVFP4 files have none of the rows the deep pick is compared on

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-18

ADR-0004 decision 8 picks the deep tier's model on fit inside the model budget, with the other
axes level. The rows behind those axes are the stop row (four written questions, three
seeds each, counted as stopped and as right by hand), the reasoning tokens a draw spends, and the
framed and unframed injection draws. They were drawn on `gemma-4-31B-it-qat` and
`Qwen3.8-27B-UD-Q4_K_M` and are in [deep candidates](../../readings/deep-candidates.md).

The two NVFP4 files the models mount holds have memory and rate rows only, in
[the NVFP4 files for the deep tier](../../readings/nvfp4-deep-tier.md). NVFP4 is another 4-bit
encoding of the same weights, so a count drawn on a Q4 file is not a count for the NVFP4 file of
that model. The gemma rows show one difference already: at draft length 1 the engine accepts 0.69
of the drafter's tokens beside the NVFP4 file against 0.85 beside the Q4 file, so the NVFP4 file's
next token differs from the drafter's more often.

What is not known:

- Whether either NVFP4 file stops on as many of the twelve stop-row draws as its Q4 file, and how
  many reasoning tokens a draw spends.
- Whether either obeys a framed or an unframed injection draw more often than its Q4 file.

What would close it: the stop row and the injection row drawn on each NVFP4 file a pick could name,
on the engine build the model host runs, with the Q4 file of the same model drawn again on that
build beside it, since the rows in deep candidates are from an older build. The drivers are named
at the end of deep candidates. The rows go into deep candidates or into the NVFP4 record, and
the choice of file is proposed in
[R-1244](1244-the-deep-tiers-file-is-not-chosen-between-the-q4-and-the-nvfp4-files.md).

## History

- 2026-11-18: filed when R-1244 drew the memory and rate rows of the two files and found that the
  rows the pick rests on do not exist for either.
