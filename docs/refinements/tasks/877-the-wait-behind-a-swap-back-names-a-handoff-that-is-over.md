# The wait behind a swap back names a handoff that is over

**Status:** open, needs a port change first
**Area:** brain-handoff
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-25

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
`ResidencyQueue` (`ports_models.py`) has only `blocks` and `await_scope_end`, so the port needs two
additions. The first is a synchronous read of the phase: the scope stays active through the restore,
and `restore_with_retries` publishes `RESIDENCY_RESTORING` on `ResidencyBoard` before it starts.
The second is a wait that also returns when the published report changes, because
`await_scope_end` returns only when the scope ends, so a wait begun while the deep model works
could not restate itself when the restore begins. `publish` already wakes the board's condition.
`ResidencyBoard` and `SwappingModelManager` implement the port, and no fake or contract test for it
exists yet: add a contract test over both. `wait_out_handoff` (`handoff_wait.py`) then restates the
wait it holds through `WaitHold.restate` when the phase changes, as
`EscalatingTurnEngine._record_swap` does for the handoff's own turn.

## History

- 2026-10-16: filed from the swap pressure flows on the Linux shell.
- 2026-10-25: premise checked against the code. `ResidencyQueue` still has no phase read and
  `RESTORING_DETAIL` is the text the board's restoring report uses, but the remedy named a fake and
  a contract test that do not exist and missed the wake on a phase change; both are corrected.
