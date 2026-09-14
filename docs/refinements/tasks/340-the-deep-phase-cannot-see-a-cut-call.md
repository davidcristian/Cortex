# The deep phase reads a cut tool call as a dead server

**Status:** landed 2026-09-14
**Area:** inference-model-manager
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

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
- 2026-09-14: **the premise holds line for line and the trigger's second limb is restated,
  because as written it was already true.** `brain_phase.py` still catches the wide
  `InferenceError` alone, at one `except` that appends `BRAIN_FAILED_NOTE`, persists and re-raises,
  and the phase still holds a `StopLedger` and still suppresses `cap_note` when it failed, so the
  fix keeps the shape described above. The two narrow consumers are exactly the two the body names,
  `engine.py` and `subagent_attempt.py`, and there is no third `except MalformedToolCallError` in
  the tree; the old limb asked for "a second consumer", which the body itself says already exists,
  so it named a state the entry was filed in rather than a change. It now names the grep that would
  show the change: a third arm appearing. The deep tier's context is still the 8192 the body cites
  (`CORTEX_CTX_SIZE_BRAIN` in the GPU override), so the size argument is unchanged. No handoff
  settling FAILED on a cut call is recorded anywhere in this repo.
- 2026-09-14: **the decision this entry calls open is smaller than it reads, and the reading is
  recorded here so the next attempt starts from it.** The phase's wide arm sets `failure`, flushes
  the channels, appends `BRAIN_FAILED_NOTE`, suppresses `cap_note` because `failure is not None`,
  persists, and re-raises. A narrow arm ahead of it would do the first of those and none of the
  rest, leaving `failure` at `None` so the capped note the phase already knows how to write is the
  one the reader gets. What the re-raise buys is one thing and it is visible in one place:
  `swap_conductor.py` catches `InferenceError` around the phase and settles the record `FAILED`
  with the exception's own message, and `MalformedToolCallError` is a subclass, so today a cut
  takes that path. An arm that does not re-raise takes the conductor's existing non-failure path
  instead, with no change to the conductor at all. So deciding what a settled-but-cut handoff is
  means choosing between two paths that both already exist, rather than building one. The size
  argument the body makes is also no longer only here: the same 8192 context and the same 3847 to
  4448 tokens are cited in a comment beside the phase's own `StopLedger`.
- 2026-09-14: **landed.** `brain_phase.py` catches `MalformedToolCallError` ahead of the wide arm,
  logs one `warning` naming the model, the session, the turn and `capped`, flushes the channels,
  and leaves `failure` unset, so the phase persists and completes and the conductor settles the
  record `DONE` on the path it already had. The open decision is answered against re-raising, and
  the argument is in the ADR-0005 deep-cut addendum: `FAILED` is a claim about the swap, every
  other reason the record carries one is a fault in the machinery, and the sibling arm on the
  cortex turn ends the same error the same way for the same reader. What the close opened is
  [R-665](665-a-settled-handoff-does-not-say-it-was-cut.md): a settled record no longer says
  whether the answer was cut, the old wrong `FAILED` having carried a sentence the right `DONE`
  does not.
