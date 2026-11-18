# The deep tier's file is not chosen between the Q4 and the NVFP4 files

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a History line in this file recording the maintainer's pick of A, B or C below.
**Verified:** 2026-11-18

On 2026-11-17 the models mount gained two files meant for the deep tier, both in NVFP4, a 4-bit
floating point weight format:

- `esatapedico/Qwen3.8-27B-NVFP4-MTP-GGUF`, a 16.91 GB model file with its draft layer inside.
- `esatapedico/Gemma-4-31B-IT-NVFP4-GGUF`, a 17.99 GB model file with no drafter.

ADR-0004 names `gemma-4-31B-it-qat` as the deep pick and `Qwen3.8-27B-UD-Q4_K_M` as the alternate.
Nothing in a tier default or a runbook names an NVFP4 file. This task was filed because the model
baseline of 2026-11-16 had no row for either file. It has them now, and what is left is the choice.

## What was measured

Both files were drawn on 2026-11-18 on engine build b12375, the build the model host runs, the way
the baseline drew the deep tier: an 18,177 MiB model budget at the peak of a row on the 24 GB card,
a 16-bit context cache, the top-down search for the largest context, the draft ladder and its stop
rule, and a split run with RAM for a file that does not fit whole. The rows and the method are in
[the NVFP4 files for the deep tier](../../readings/nvfp4-deep-tier.md), beside the baseline's rows
for the two Q4 files.

- **The engine loads both** and holds the weights on the card in their 4-bit form. It logs no
  conversion.
- **Qwen3.8-27B NVFP4 fits whole, with 302 MiB less card memory than the Q4 file at the same
  context.** Its largest context with the draft layer is 32K, at draft length 1 only, against 24K
  for the Q4 file. Without drafting both stop at 40K. Without drafting it writes 1.10 to 1.12 of
  the Q4 file's rate, and its prompt pass is 1.8 to 2.0 of the Q4 file's. With drafting its best
  rate is under the Q4 file's best at each context drawn in both: 0.94 at 16K, 0.92 at 20K and
  0.96 at 24K. Its best draft length is 2 at 20K and 24K and 4 at 16K, against 5, 3 and 5 for the
  Q4 file.
- **gemma-4-31B NVFP4 does not fit whole at any context**, as the Q4 file does not, and needs 756
  MiB more of the card. Split with RAM it keeps two layers fewer on the card and writes 0.87 of
  the Q4 file's rate at 16K and 0.68 at 32K. The engine accepts the Q4 file's drafter beside it,
  but no draft length is faster than no drafting, where the Q4 file gains 1.24 at 16K.

## What is not known

- What either NVFP4 file writes. The stop row, the reasoning count and the injection rows that
  ADR-0004 decision 8 picks on were never drawn for them:
  [R-1245](1245-the-nvfp4-files-have-none-of-the-rows-the-deep-pick-is-compared-on.md).
- How the card multiplies the NVFP4 type. The engine's log does not say, and no other build was
  run.
- The same rows with an 8-bit context cache, which
  [R-1243](1243-every-tier-holds-its-context-in-the-default-16-bit-cache.md) draws for every model
  and can now draw for these two.
- Whether another drafter suits the gemma NVFP4 file better. The mount holds one drafter for this
  model.

## The choice

Which file the deep tier names is the maintainer's pick. The deep tier has no default artifact, so
the choice changes the file ADR-0004 names for an entry, and no compose default.

- **A. Change nothing.** The pick stays `gemma-4-31B-it-qat` and the alternate stays
  `Qwen3.8-27B-UD-Q4_K_M`.
- **B. The alternate's file becomes the Qwen NVFP4 file; the pick's file stays.**
- **C. Both entries name their NVFP4 file.**

Recommended: A now, and B once R-1245 has drawn the Qwen NVFP4 file's rows and they are no worse
than the Q4 file's. The Qwen NVFP4 file takes less of the card, reads a prompt nearly twice as
fast and writes faster without drafting, and its lower rate with drafting is the one cost.
[R-739](739-the-deep-tier-cannot-name-a-drafter-built-into-its-own-model.md) applies to it as it
does to the Q4 file, so a deployment of either drafts nothing today. C is not recommended on these
rows: the gemma NVFP4 file costs more card memory, writes more slowly in the split run this budget
needs, and gets nothing from the drafter ADR-0004 recommends with the pick.

## History

- 2026-11-17: filed when the user started the two downloads, as the second of three follow-ups to
  the model baseline.
- 2026-11-18: both files drawn on build b12375 and recorded in the readings above. The task now
  waits for the pick, and its title and file name say so. R-1245 filed for the rows the pick is
  compared on.
