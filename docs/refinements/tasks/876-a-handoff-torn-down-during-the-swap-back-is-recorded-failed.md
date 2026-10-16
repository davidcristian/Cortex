# A handoff torn down during the swap back is recorded failed

**Status:** open, actionable
**Area:** brain-handoff
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-16

`SwapConductor._run_claimed` (`cortex_core/swap_conductor.py`) settles a handoff `FAILED` with
`TORN_DOWN_REASON`, "the turn was torn down before the handoff finished", for any exception that
leaves the swap, and the brain logs `a handoff ended failed` with that reason. On the Linux shell
two handoffs were recorded that way although the reason was wrong
([readings](../../readings/overlay-swap-pressure-flows.md)):

- **A new chat during the swap back.** `Ctrl+N` 0.5 s after the deep model stopped, while the chip
  read "bringing the usual assistant back". The deep phase had stored its reply, the swap back
  finished, and the record stayed in Redis as `failed` with the torn down reason for its hour.
- **A full Redis during the deep phase.** The deep reply's append failed with `SessionStoreError`,
  which left the swap the same way and was logged with the same reason, though no one tore the turn
  down.

An operator reading the log or the record cannot tell a handoff that answered from one that never
loaded.

## Reproduction

On the shared stack, the `just rpc-handoff` prompt in the overlay, the card approved; once
`GET /models/brain` reads `stopped` after `ready`, press `Ctrl+N`. Read `cortex:handoff:<turn id>`
in Redis and the brain's `a handoff ended failed` line.

## What to do

Give the reason the phase the swap reached. Track in `_run_claimed` whether the swap has yielded
`RESTORING_DETAIL` (the deep reply is stored by then), and settle a teardown after it with a reason
such as "the turn was torn down during the swap back, after the deep model's reply was stored". Give
a `SessionStoreError` from the deep phase its own reason, "the deep model's reply could not be
stored". Both are new constants in `swap_reasons.py`, with conductor tests over the fakes for each
and the module doc's list of reasons updated.

## History

- 2026-10-16: filed from the swap pressure flows on the Linux shell.
