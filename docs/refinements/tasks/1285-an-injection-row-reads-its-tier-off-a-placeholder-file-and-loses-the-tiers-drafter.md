# An injection row reads its tier off a placeholder file and loses the tier's drafter

**Status:** done 2026-11-23
**Area:** untrusted-content
**Origin:** [ADR-0060](../../adr/ADR-0060-injection-rows-follow-the-tier.md)

`tier_args` in `brain/packages/inference/tests/test_injection_defense_live.py` reads every tier
off one `ModelHostConfig` whose three files are the placeholder `any/artifact.gguf` (`_CONFIG`),
and `server_argv` substitutes the row's real file afterwards. The model host computes a tier's
drafter flags from the tier's file, so the placeholder changes them. Read on 2026-11-21 by
printing both command lines, with no server started:

- **The cortex pick.** `ModelHostConfig(cortex_file=...)` with the pick's file gives the tier
  `--model-draft /models/unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf --spec-type
  draft-mtp --spec-draft-n-max 3` after `--cache-ram 8192`. The harness's row for the same file
  ends at `--cache-ram 8192`, because the placeholder has no drafter beside it.
- **The deep pick with `CORTEX_MODEL_FILE_BRAIN_DRAFT` naming the deep file**, which is how a
  deployment drafts with the layer inside it. The model host writes `--spec-type draft-mtp
  --spec-draft-n-max 3` and no `--model-draft`. The harness's row writes `--model-draft` with the
  deep file's path, which names the file as a second model, because the drafter's path is
  compared with the placeholder.

On the defaults a deep row names no drafter and equals the tier's command line.
`test_a_shipped_row_is_its_tiers_own_command_line` builds the tier it compares with from the same
placeholder, so it passes in both cases above.

## Proposal

Build a row's tier from a `ModelHostConfig` that names the row's own file, and compare each
candidate's row with the model host's command line for that file. The cortex pick's rows then
draft, which changes what they count: write the pass rule first, then draw the pick's row with and
without the drafter.

**What closes it.** A row whose drafter flags equal the model host's for the same file, compared
by a test CI runs, or a decline that says why a row does not draft.

## History

- 2026-11-21: filed when the deep row's tail was compared with its tier's.
- 2026-11-23: Closed. `tier_args` builds the tier from a `ModelHostConfig` naming the row's own
  file, and in the subagent tier's tail the switch takes the place of the reasoning-off pair while
  the flags after it stay on the card. The subagent pick lost its drafter the same way. With no
  server started, every candidate's shipped row now equals the model host's command line for its
  file, the deep pick drafting with its own file included, and `test_switch_rows.py` compares
  them. Drawing the picks' rows with the drafter is
  [R-1313](1313-the-picks-injection-rows-have-not-been-drawn-with-their-drafters.md).
