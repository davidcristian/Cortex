# The wait behind a swap back names a handoff that is over

**Status:** open, needs a port change first
**Area:** brain-handoff
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-16

A turn that meets another turn's handoff waits for the residency scope to end and shows
`HANDOFF_AHEAD_DETAIL`, "waiting for another request's handoff to the deep model to finish"
(`cortex_core/handoff_wait.py`). On the Linux shell a person pressed `Ctrl+N` during a handoff and
asked a new question at once, once while the deep model loaded and once while the cortex came back
([readings](../../readings/overlay-swap-pressure-flows.md)). In both the new chat showed that chip
for the 40 s it waited, though the person had just left that request and the brain was only
reloading the cortex.

## Reproduction

On the shared stack, the `just rpc-handoff` prompt in the overlay, the card approved, then `Ctrl+N`
while the deep model loads and "What is 5 plus 5? One line." sent in the new chat. Read the chip
under the new question.

## What to do

Show the swap back's own words, `RESTORING_DETAIL` ("bringing the usual assistant back"), while the
scope ahead is restoring the cortex, and the current text while the deep model loads or works.
`ResidencyQueue` has only `blocks` and `await_scope_end`, so the port needs a way to read the
phase, for example the residency state the board already publishes (`RESIDENCY_RESTORING`), with
the fake and its contract test extended to match. A wait already shown is restated when the phase
changes, as `EscalatingTurnEngine._record_swap` does for the handoff's own turn.

## History

- 2026-10-16: filed from the swap pressure flows on the Linux shell.
