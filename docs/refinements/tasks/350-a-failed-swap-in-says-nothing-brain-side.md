# A swap that failed on the model host says nothing in the brain's own log

**Status:** landed 2026-08-22
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
- 2026-08-22: Landed as the ADR-0030 failed-reason addendum, as the third shape: a `failure` field
  on the handoff record, written by the settling transition through a widened `HandoffStore.transition`
  and a `HandoffSettler.fail` that no caller can reach without a reason. The record was chosen over
  the two log-only shapes because it is the only one that survives the process, which is what a
  reader of a `FAILED` record has, and because the write that puts it there is also where the line
  belongs, so the cheaper shape came with it rather than instead of it. Every way a handoff can end
  failed now says which: three app-authored sentences in a new `swap_reasons.py` (the drain abort,
  the teardown, the boot that found the record stranded) and, on the two paths that arrive as an
  exception, that exception's own message, which is where the model host's status code and response
  body reach the brain's side. The three user-facing notes are untouched. Re-derivation found one
  claim of this entry's overstated: the fit check inside `swap_in` already logged both of its
  refusals at `ERROR`, so "the swap in keeps nothing" was true of the eviction, the load and the
  gate and false of the two refusals above them. What the close opened, that the reason is now
  written to two surfaces neither of which anything reads back, is
  [R-379](379-a-settled-reason-nothing-reads-back.md).
