# The deep phase reads a cut tool call as a dead server

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** the first handoff observed settling FAILED whose partial answer ends mid tool call, or
a second consumer of the narrower error growing a reason to tell the two apart

Both consumers that can act on `MalformedToolCallError` now do: a delegated attempt reports a
truncation rather than an inference failure, and the cortex turn ends with a note rather than
raising. `BrainPhase` is the third and reads the wide `InferenceError`, so a completion cut while
the deep model was writing a tool call's `arguments` streams `BRAIN_FAILED_NOTE`, persists, and
re-raises, and the conductor settles the record FAILED.

Two things are wrong with that and one is not. The note is not wrong: it says the deep model
stopped partway and the text above is everything it produced, which is true of a cut. What it does
not say is that a length limit did it, so the reader is never told the one thing they could act on,
and the record reads FAILED for a completion that was merely cut, which is a fact about the machine
that was not true.

The deep tier is where this is likeliest rather than rarest, which is the reverse of the cortex's
case. It ships an 8192 context and the measured pick spends 3847 to 4448 tokens reaching an answer
(the ADR-0004 brain-pick table), and it carries the cortex turn's own bounds besides, so the limit
is one long question away.

The fix has the cortex's shape and one extra decision. The phase already holds a `StopLedger` and
already suppresses `cap_note` when it failed, so the arm is a narrower `except` ahead of the wide
one that appends the capped note instead of the failure note. The decision is whether it still
re-raises: the conductor's `FAILED` is what stops a handoff being retried, and a cut is not a
failure of the swap, so answering that question means deciding what a settled-but-cut handoff is.

## Trail

- 2026-08-20: Opened by the close of
  [R-297](297-cut-tool-call-fails-the-cortex-turn.md), which gave the cortex turn the arm and left
  the phase that continues it. Recorded in the ADR-0005 cortex-cut addendum.
