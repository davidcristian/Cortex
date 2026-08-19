# A bool loses which of two models the restore failed on

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`restore_standing` now fails in two places that name two different models: the eviction of the
model the handoff swapped in, and the start of the cortex it is putting back. Each says which it
was. What it answers its caller is still a bool, so the distinction stops at the function boundary,
and `restore_with_retries` writes `restoring the cortex failed; retrying` with `model` set to the
cortex whichever of the two actually failed. Its give-up a moment later does the same, in a line
and in the `ResidencyRestoreError` message an operator reads out of the runbook.

That is the same two-candidate-subjects fault one level up, and it is milder for two reasons worth
writing down rather than rediscovering. The line immediately above it carries the honest name, so
the pair read together is complete, and the retry line is genuinely about the operation rather than
about a model: what is being retried is the restore, and the restore is of the cortex. The give-up
is the weaker of the two, since "could not restore 'cortex'" is what an operator carries to the
runbook and the tier that actually refused may have been the other one.

Closing it means `restore_standing` answering something richer than a bool: which model the attempt
failed on, or nothing when it succeeded. That is a signature change to a function three modules
call, and it pushes a value through `restore_with_retries` whose only consumer is a log line and an
error message, which is exactly the shape the failed-turn entry weighs and does not pick. It should
not be taken on its own; the honest version is to ask at the same time whether the give-up error
itself should name the refused tier, since that is the sentence the runbook sends a person to.

## Trail

- 2026-08-19: Opened by the close of
  [329](329-a-failure-with-two-candidate-subjects.md), which narrowed the two blocks and found the
  residue at the caller that reads their verdict.
