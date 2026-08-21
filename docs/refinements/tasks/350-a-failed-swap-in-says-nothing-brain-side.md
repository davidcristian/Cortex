# A swap that failed on the model host says nothing in the brain's own log

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-21 by the close of
[R-345](345-a-refusal-that-is-not-the-only-record.md), whose survey of every brain-side caller of
the model host's per-model routes found six that write the daemon's sentence into the brain's log
and one that keeps nothing. The one is the swap in, and it is the path a user is waiting on.

`swap_in` in `brain/packages/core/src/cortex_core/residency_moves.py` puts the `ModelHostError` it
caught into a `SwapFailedError`, so the daemon's own words are carried. `swap_conductor._swap`
catches that as a `ModelManagerError`, settles the handoff record `FAILED` through
`HandoffSettler.advance`, which takes a state and no reason, and answers `note_for(err)`, which maps
the error's type to one of three fixed user-facing sentences and never reads `str(err)`. Nothing
between those two points logs anything. So a handoff that died because the cortex would not evict,
or because the deep model's start was refused, leaves the brain's log with no line naming what
happened, and the record it settles carries a state and nothing else.

The reason does exist, in the `model-host` sidecar's own container log, at `ERROR`, under the
greppable sentence `a model-host request failed`. That is the line the refusal-reach addendum
found is the only record on this path. Reading it means knowing to look in a different container's
log for the cause of a failure the brain reported, which is exactly the correlation an operator is
worst placed to make while a user is waiting.

**Why it is not simply a missing log call.** The three notes exist because the user is told what is
true of the GPU rather than what broke, and that stays right. The question is what the brain writes
for itself, and there are at least three shapes: a line at the conductor's catch, which is one call
and says the least about which move failed; a line at each raise inside `swap_in`, which is where
the move is known and is the shape the swap back already uses; or a reason on the handoff record,
which is the only one that survives the process and the only one a later reader of a `FAILED`
record could use, and which needs a field the record does not have. The record's shape is the
decision, not the log call.

**What would close it.** Pick one of the three, with the record's shape decided rather than
deferred, and keep the user-facing note exactly as it is. If the answer is the cheapest one, say so
against the other two rather than by omission.

## Trail

- 2026-08-21: opened by the close of [R-345](345-a-refusal-that-is-not-the-only-record.md), whose
  seven-caller survey found this one keeps nothing at all.
