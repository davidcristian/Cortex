# The deep phase reads a cut tool call as a dead server

**Status:** done 2026-09-14
**Area:** inference-model-manager
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

Two consumers act on `MalformedToolCallError`: a delegated attempt reports a truncation rather than
an inference failure, and the cortex turn ends with a note rather than raising. `BrainPhase` is the
third and catches the wide `InferenceError`, so a completion cut while the deep model was writing a
tool call's `arguments` streams `BRAIN_FAILED_NOTE`, persists, and re-raises, and the conductor
settles the record FAILED.

The note itself is right: it says the deep model stopped partway and the text above is everything
it produced, which is true of a cut. What it does not say is that a length limit did it, so the
reader is never told the one thing they could act on, and the record reads FAILED for a completion
that was merely cut.

The deep tier is where this is likeliest. It ships an 8192 context and the measured choice uses
3847 to 4448 tokens reaching an answer (the ADR-0004 brain-pick table), and it also holds the
cortex turn's own bounds, so the limit is one long question away.

The fix has the cortex's shape and one extra decision. The phase already has a `StopLedger` and
already suppresses `cap_note` when it failed, so the change is a narrower `except` ahead of the
wide one that appends the capped note instead of the failure note. The decision is whether it still
re-raises: the conductor's `FAILED` is what stops a handoff being retried, and a cut is not a
failure of the swap.

## History

- 2026-08-20: Opened by the close of [R-297](297-cut-tool-call-fails-the-cortex-turn.md), which
  gave the cortex turn the narrow branch and left the phase that continues it. Recorded in
  ADR-0048.
- 2026-09-14: The premise holds line for line, and the trigger's second half was restated because
  as written it was already true. `brain_phase.py` still catches the wide `InferenceError` alone,
  at one `except` that appends `BRAIN_FAILED_NOTE`, persists and re-raises. The two narrow
  consumers are `engine.py` and `subagent_attempt.py`, and there is no third `except
  MalformedToolCallError` in the tree, so the old wording asked for something that already existed.
  The deep tier's context is still 8192 (`CORTEX_CTX_SIZE_BRAIN` in the GPU override). No handoff
  settling FAILED on a cut call is recorded anywhere in this repo.
- 2026-09-14: The open decision is smaller than it reads. The phase's wide branch sets `failure`,
  flushes the channels, appends `BRAIN_FAILED_NOTE`, suppresses `cap_note` because `failure is not
  None`, persists, and re-raises. A narrow branch ahead of it would do the first of those and none
  of the rest, leaving `failure` at `None` so the capped note the phase already writes is what the
  reader gets. What the re-raise buys is visible in one place: `swap_conductor.py` catches
  `InferenceError` around the phase and settles the record `FAILED` with the exception's own
  message, and `MalformedToolCallError` is a subclass. A branch that does not re-raise takes the
  conductor's existing non-failure path, with no change to the conductor.
- 2026-09-14: Fixed. `brain_phase.py` catches `MalformedToolCallError` ahead of the wide branch,
  logs one `warning` naming the model, the session, the turn and `capped`, flushes the channels,
  and leaves `failure` unset, so the phase persists and completes and the conductor settles the
  record `DONE` on the path it already had. The open decision is answered against re-raising, with
  the argument in ADR-0048: `FAILED` is a claim about the swap, every other reason the record has
  one is a fault in the machinery, and the matching branch on the cortex turn ends the same error
  the same way. It opened [R-665](665-a-settled-handoff-does-not-say-it-was-cut.md): a settled
  record no longer says whether the answer was cut.
