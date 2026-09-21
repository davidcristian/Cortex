# A bool loses which of two models the restore failed on

**Status:** done 2026-08-20
**Area:** inference-model-manager
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`restore_baseline` fails in two places that name two different models: the eviction of the model
the handoff swapped in, and the start of the cortex it is putting back. Each line says which it
was. What the function returns is a bool, so the difference stops at the function boundary, and
`restore_with_retries` writes `restoring the cortex failed; retrying` with `model` set to the
cortex whichever of the two actually failed. Its give-up a moment later does the same, in a line
and in the `ResidencyRestoreError` message an operator reads out of the runbook.

That is the same two-candidate fault one level up, and it is milder: the line immediately above has
the correct name, and the retry line is about the operation rather than a model, since what is
retried is the restore of the cortex. The give-up is the weaker of the two, because "could not
restore 'cortex'" is what an operator takes to the runbook and the tier that actually refused may
have been the other one.

Closing it means `restore_baseline` returning which model the attempt failed on, or nothing when it
succeeded, and asking at the same time whether the give-up error should name the refused tier.

## History

- 2026-08-19: Opened by the close of [329](329-a-failure-with-two-candidate-subjects.md), which
  narrowed the two blocks and found the remainder at the caller that reads their result.
- 2026-08-20: Fixed as ADR-0051 decision 7, with the paired question answered at the same time.
  `restore_baseline` returns `str | None`: `None` is the permanent residency being back, and
  anything else is the model this attempt failed on, which is the swapped-in resident when the
  eviction refused and the cortex when its start refused or it never reported ready. The retry line
  keeps `restoring the cortex failed; retrying`, this entry's reading of it having held, and both
  it and the give-up now attach `failed_model` beside the unchanged `model`, which are two facts
  rather than one. The paired question is a yes: `ResidencyRestoreError` reads `could not restore
  'cortex' after 2 attempts, the last of which failed on 'brain'; manual recovery is needed`, since
  that string is what an operator takes to the runbook and it was sending them to a tier whose
  `start` never ran. `docs/runbooks/model-swap.md` gains the paragraph that makes the named tier
  actionable. The cost estimate here was wrong: this is not a signature change to a function three
  modules call. `restore_baseline` has exactly one production caller, and the other two mentions
  are prose in a test module and in the model host's contract suite, so the change was a return
  type, one call site and two sentences. Six mutations were measured over the whole brain
  workspace; the one that matters fixes the retry line's `failed_model` to the cortex, which only
  the eviction case catches.
