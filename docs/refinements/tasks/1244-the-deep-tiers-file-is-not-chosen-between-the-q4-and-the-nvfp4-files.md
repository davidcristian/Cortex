# The deep tier's file is not chosen between the Q4 and the NVFP4 files

**Status:** open, waiting for its trigger
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a History line in this file recording the maintainer's pick of A, B or C below.
**Verified:** 2026-11-22

On 2026-11-17 the models mount gained two files meant for the deep tier, both in NVFP4, a 4-bit
floating point weight format:

- `esatapedico/Qwen3.8-27B-NVFP4-MTP-GGUF`, a 16.91 GB model file with its draft layer inside.
- `esatapedico/Gemma-4-31B-IT-NVFP4-GGUF`, a 17.99 GB model file with no drafter.

ADR-0004 names `Qwen3.8-27B-UD-Q4_K_M` as the deep pick and `gemma-4-31B-it-qat` as the alternate.
Nothing in a tier default or a runbook names an NVFP4 file. This task was filed because the model
baseline of 2026-11-16 had no row for either file. It has them now, and what is left is the choice.

## What was measured

Memory and rate rows are in two records:
[the Q4 and NVFP4 deep files on one night](../../readings/nvfp4-deep-pair.md) for 16K, and
[the NVFP4 files for the deep tier](../../readings/nvfp4-deep-tier.md) for the loader facts and
the other contexts. What the Qwen NVFP4 file writes is in
[its count rows](../../readings/nvfp4-deep-counts.md). All are on engine build b12375, the build
the model host runs, under the baseline's 18,177 MiB model budget on the 24 GB card.

- **The engine loads both NVFP4 files** and holds the weights on the card in their 4-bit form.
  It logs no conversion.
- **Both Qwen files were drawn on one night, 2026-11-22, in the shape the tier ships in**: the
  model host's launch at 16384 with the file's draft layer at length 3 and the `q8_0` cache, the
  files in turn, every row at one power limit. By the mean of twelve texts the NVFP4 file writes
  0.943 of the Q4 file's rate, and 0.968 by the median, with two standard errors of 0.059. It is
  not shown to write at another rate, and every reading is under 1; three texts had read 1.014.
  Its prompt pass is 1.79 of the Q4 file's over four launches of each. It takes 190 MiB less of
  the card, 16,806 against 16,996 MiB, and both files fit with 2,700 MiB or more free where
  1,536 are kept.
- **The other cells of that night.** At `f16` with the draft layer the NVFP4 file writes 0.928
  of the Q4 file's rate, more than two standard errors under it. Without a drafter it reads
  1.023 at `q8_0` and 1.045 at `f16`, on three texts and on launches up to 0.040 apart. Each
  file's 8-bit rate is 0.94 to 1.00 of its 16-bit rate, with 452 to 490 MiB less.
- **Draft length.** The Q4 file's fastest length is 5 at both cache types, at 1.007 and 1.014
  of length 3. The NVFP4 file's is 4 at `f16`, at 1.020, and 2 at `q8_0`, where length 2 read
  1.049 of length 3 on each of two sets of three texts, about one standard error.
- **A deep reply's time**, the prompt pass and then 1,000 tokens written. The NVFP4 file takes
  1.04 of the Q4 file's time on a 900-token handoff prompt and 0.90 on the 10,863 tokens of a
  full history window. The load is left out, and so is the first prompt pass after a load.
- **What the Qwen NVFP4 file writes.** Three stop cells, the injection text rows at `medium` and
  one handoff through the brain were drawn on 2026-11-22, and no count reads apart from the Q4
  file's. In that handoff its first prompt pass after the load took 1.8 times as long as the Q4
  file's of 2026-11-21
  ([R-1290](1290-the-qwen-nvfp4-files-first-prompt-pass-after-a-load-is-slower-in-one-handoff.md)).
- **At other contexts the ratios divide rows of two nights**
  ([R-1259](1259-the-same-launch-reads-a-different-rate-on-another-night.md)). The memory rows
  do not depend on the night: with the 16-bit cache the NVFP4 file's largest context with the
  draft layer is 32K, at draft length 1 only, against 24K for the Q4 file, and without drafting
  both stop at 40K. With the 8-bit cache both reach 48K with the layer, and without it the NVFP4
  file reaches 80K against 64K ([readings](../../readings/kv-cache-types.md)).
- **gemma-4-31B NVFP4 does not fit whole at any context**, as the Q4 file does not, and the
  engine projects 756 MiB more of the card for it. Split with RAM at 16K on 2026-11-22, both
  files in turn, it keeps two layers fewer on the card and writes 0.850 of the Q4 file's rate
  without drafting and 0.667 at draft length 1. With the drafter the Q4 file writes 1.25 times
  its own no-draft rate there and the NVFP4 file 0.98. At 32K its 0.68 divides rows of two
  nights. With an 8-bit cache it writes 1.52 and 1.56 times its 16-bit rate at 16K split with
  RAM, with no fall in card memory
  ([the rows of 2026-11-20](../../readings/kv-cache-remaining-cells.md)).

## What is not known

- What the gemma NVFP4 file writes. It has none of the rows the deep pick is compared on:
  [R-1245](1245-the-nvfp4-files-have-none-of-the-rows-the-deep-pick-is-compared-on.md).
- Whether the Qwen NVFP4 file's first prompt pass after a load is slower when both files are
  drawn on one date, and whether that grows with the prompt (R-1290). The reply time above
  leaves it out, and it decides whether the faster prompt pass reaches a handoff.
- Whether the two Qwen files differ in the shipped shape by less than 0.06. Twelve texts a file
  do not tell a smaller difference from none.
- Whether draft length 2 is faster than 3 for the Qwen NVFP4 file at `q8_0`. Six texts a length
  read 1.05 to 1.06 with a standard error of about 0.04.
- The Qwen NVFP4 file's injection rows at `xhigh` and its undrafted `xhigh` stop cell
  ([R-1289](1289-the-qwen-nvfp4-file-has-no-injection-row-at-xhigh-and-no-undrafted-xhigh-stop-cell.md)).
- How the card multiplies the NVFP4 type. The engine's log does not say, and no other build was
  run.
- The gemma NVFP4 file in the shape the stack starts the tier in, every layer on the card
  ([the Q4 file's rows](../../readings/kv-cache-deep-whole.md)), and the gemma pair at 32K on
  one night. Whether another drafter suits that file better: the mount holds one for the model.

## The choice

Which file each deep entry names is the maintainer's pick. The deep tier has no default artifact, so
the choice changes the file ADR-0004 names for an entry, and no compose default for a file.

- **A. Change nothing.** The pick stays `Qwen3.8-27B-UD-Q4_K_M` and the alternate stays
  `gemma-4-31B-it-qat`, each its Q4 file.
- **B. The pick's file becomes the Qwen NVFP4 file; the alternate's file stays.**
- **C. Both entries name their NVFP4 file.**

**What B changes beside the file's name**, each read in the tree on 2026-11-22:

- **The lineup.** ADR-0004's lineup table and its decision 8 name `Qwen3.8-27B-UD-Q4_K_M`.
- **The cache type default.** ADR-0077 decision 8 tells a deployment that names an NVFP4 file
  to set `CORTEX_KV_CACHE_TYPE_BRAIN=f16`, and says a choice that moves the pick moves the
  default back to `f16`. It rests on one row: the rule of
  [the cache type readings](../../readings/kv-cache-types.md) reads the rate "at every context
  where both types have a row", and the file writes 0.81 of its 16-bit rate at 32K at draft
  length 1 (2026-11-18). At 16384, the context the tier ships at, the rows of 2026-11-22 meet
  all four conditions: the model host starts the file at `q8_0`; it takes 469 to 490 MiB less,
  where the rule asks for 250; its 8-bit rate is 0.937 of its 16-bit rate without a drafter
  and 0.977 by the mean of twelve texts at draft length 3, where the rule asks for 0.90, with
  the prompt pass at 1.01 to 1.04; and the output check passed for the file on 2026-11-19
  ([every model](../../readings/kv-cache-every-model.md)). So the rule as written still gives
  `f16` for this file, and the same rule read at the shipped context gives `q8_0`. B includes
  deciding which reading the default follows. At `f16` the tier takes 490 MiB more and reads
  0.966 of the Q4 file as shipped. No default was changed on these rows.
- **The draft length.** `DEFAULT_BRAIN_DRAFT_LENGTH` in
  `brain/packages/model_manager/src/cortex_model_manager/config.py` is 3 for whichever file a
  deployment names. No row shows another length faster for the NVFP4 file, so B changes
  nothing there.
- **The runbook.** [The model swap runbook](../../runbooks/model-swap.md) names the Q4 file's
  path as `CORTEX_MODEL_FILE_BRAIN` and gives the pick's cost for `CORTEX_SWAP_BRAIN_VRAM_MIB`
  as 15950 MiB without its drafter and 16991 with its draft layer. The NVFP4 file's highest
  readings of 2026-11-22 are 15,671 to 15,685 MiB and 16,803 to 16,898 MiB. A deployment of
  either Qwen file drafts with the file's own layer when `CORTEX_MODEL_FILE_BRAIN_DRAFT` names
  that file.

**What C changes beside that**: the alternate's entry in ADR-0004, and the runbook's line for
the alternate's drafter, since no draft length is faster than no drafting for the gemma NVFP4
file. Under A nothing changes.

**Proposed, not chosen: A.** The rows of 2026-11-22 give no reason to move the pick's file. In
the shape the tier ships in the NVFP4 file is not shown to write faster, and every reading puts
it under the Q4 file. Its counts do not read apart. Both files fit at 16384 with room, so 190
MiB less changes nothing the tier does there. B would be the better choice for one kind of use:
handoffs that send a long prompt and get a short reply, where the prompt pass at 1.79 of the Q4
file's makes the reply 0.90 of the Q4 file's time at a full history window with 1,000 tokens
written, and only if R-1290 shows that the first prompt pass after a load does not take that
back. C is not proposed: the
gemma NVFP4 file writes 0.850 of the Q4 file's rate in the split run this budget needs, gets
nothing from the drafter ADR-0004 names for the alternate, and holds more of the card.

## History

- 2026-11-17: filed when the user started the two downloads, as the second of three follow-ups to
  the model baseline.
- 2026-11-18: both files drawn on build b12375 and recorded in the readings above. The task now
  waits for the pick, and its title and file name say so. R-1245 filed for the rows the pick is
  compared on.
- 2026-11-19: the trigger has not fired: no History line records a pick. Both Qwen files were
  drawn at 20K on one night after the same launch read a different rate on another night, and the
  NVFP4 file's no-draft advantage reads 1.05 there, not 1.11. The 8-bit rows of R-1243 were added
  where the files are compared. The recommendation is unchanged. R-1259 filed for the difference
  between nights.
- 2026-11-20: the trigger has not fired: no History line records a pick. The deep tier's cache
  type default became `q8_0` on the rows of both Q4 files, and the choice above now says what
  each option does to it. The gemma NVFP4 file's split rows at 8 bits were added where the files
  are compared.
- 2026-11-20: the maintainer made `Qwen3.8-27B-UD-Q4_K_M` the deep pick and `gemma-4-31B-it-qat`
  the alternate (ADR-0004 decisions 5 and 8). That picks between the two models, each on its Q4
  file, and is none of A, B or C, so the trigger has not fired. The three choices are written
  for that pick: B now moves the pick's file, and with it the cache type default.
- 2026-11-21: the maintainer asked for both files of the pick to be drawn again on one night,
  under the model baseline's conditions, before choosing.
- 2026-11-22: the trigger has not fired: no History line records a pick. Both Qwen files were
  drawn on one night at 16384 in the shape the tier ships in, every row at one power limit:
  eight cells on three texts, the four drafted cells again on twelve texts, a draft ladder for
  each file at each cache type, and the gemma pair split with RAM. The Qwen NVFP4 file's stop,
  injection and handoff counts were drawn the same night (R-1245). What was measured, what is
  not known and the choice are written on those rows. The proposal is A.
