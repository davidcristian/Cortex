# A swap that failed on the model host writes nothing in the brain's own log

**Status:** done 2026-08-22
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Of the seven brain-side callers of the model host's per-model routes, six write the daemon's
sentence into the brain's log and one keeps nothing. The one is the swap in, the path a user is
waiting on.

`swap_in` in `brain/packages/core/src/cortex_core/residency_moves.py` puts the `ModelHostError` it
caught into a `SwapFailedError`, so the daemon's own words are kept. `swap_conductor._swap` catches
that as a `ModelManagerError`, settles the handoff record `FAILED` through
`HandoffSettler.advance`, which takes a state and no reason, and replies with `note_for(err)`,
which maps the error's type to one of three fixed user-facing sentences and never reads `str(err)`.
Nothing between those two points logs anything. So a handoff that died because the cortex would not
evict, or because the deep model's start was refused, leaves no line in the brain's log naming what
happened.

The reason exists in the `model-host` sidecar's own container log, at `ERROR`, under the sentence
`a model-host request failed`. Reading it means knowing to look in a different container's log for
the cause of a failure the brain reported.

Three possible fixes: a line at the conductor's catch, which is one call and says the least about
which move failed; a line at each raise inside `swap_in`, which is where the move is known and is
what the swap back already does; or a reason on the handoff record, the only one that survives the
process and the only one a later reader of a `FAILED` record could use, which needs a field the
record does not have. The record's shape is the decision, not the log call. The user-facing note
stays exactly as it is.

## History

- 2026-08-21: Opened by the close of [R-345](345-a-refusal-that-is-not-the-only-record.md), whose
  seven-caller survey found this one keeps nothing at all.
- 2026-08-22: Fixed as ADR-0030 decision 10, taking the third option: a `failure` field on the
  handoff record, written by the settling transition through a widened `HandoffStore.transition`
  and a `HandoffSettler.fail` that no caller can reach without a reason. The record was chosen over
  the two log-only options because it is the only one that survives the process, and because the
  write that puts it there is also where the line belongs, so the cheaper option came with it
  rather than instead of it. Every way a handoff can end failed now says which: three sentences
  this repo writes in a new `swap_reasons.py` (the drain abort, the teardown, the boot that found
  the record stranded) and, on the two paths that arrive as an exception, that exception's own
  message. The three user-facing notes are untouched. One claim of this entry was overstated: the
  fit check inside `swap_in` already logged both of its refusals at `ERROR`, so "the swap in keeps
  nothing" was true of the eviction, the load and the readiness wait and false of the two refusals
  above them. What the close opened, that the reason is now written to two places neither of which
  anything reads back, is [R-379](379-a-settled-reason-nothing-reads-back.md).
