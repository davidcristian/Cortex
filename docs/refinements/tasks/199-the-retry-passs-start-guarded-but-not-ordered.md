# The retry pass's start guarded but not ordered

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Trigger:** a record under `docs/readings/`, `docs/host/` or `docs/runbooks/` of a live handoff
run with `CORTEX_ESCALATION` and a non-empty `CORTEX_SWAP_EVICT_MODELS`, in which a peer a retry
pass had just started made the fit check refuse (with `CORTEX_SWAP_BRAIN_VRAM_MIB` set) or left the
handoff overcommitted (with `CORTEX_SWAP_BRAIN_DECODE_TPS` set). All four default off.
`grep -rlni 'retry pass' docs/readings docs/host docs/runbooks` finding nothing says there is no
such record.
**Verified:** 2026-10-07

A retry pass reads the handoff claim and the residency scope flag synchronously in the instant
before it starts a tier, so a handoff cannot begin between the check and the call. What is not
excluded is the other order: a `start` already sent when a handoff begins, whose request the daemon
serves after the swap in's own `stop` of that same tier, leaving a peer loading beside the deep
model. Reaching it means one loopback request outliving the claim, the whole drain, the lease wait,
a `boot_id` round trip and a full cortex stop, so it is narrow. Under `CORTEX_SWAP_CORESIDENT` the
swap stops no peer and skips the drain, so there the start need only allocate after the fit
check's reading.

The two outcomes are not equally cheap. The fit check reads the card between the last eviction and
the deep load, so it refuses the handoff only when the peer had already allocated by that reading. A
start the daemon serves after it contributes nothing to the figure compared, and the peer runs until
`restart_evicted` finds it already up. That second outcome is a handoff that succeeds
overcommitted, which is the case `cadence.py` was written for: both tiers report ready, free memory
afterwards looks like a fit, and throughput is roughly halved. No state is lost and no record is
corrupted, which is what ADR-0054 decision 4 states; the deep phase's decode rate is not covered by
that claim.

The fix is a primitive that orders the two calls rather than a wider flag. The obvious one is
refused: taking the GPU lease for the start would park a user's turn behind a control call and can
block a pass for the whole load bound.

## History

- 2026-08-11: Opened by the tier retry pass's close, which owns the check and says plainly what it
  does not cover.
- 2026-09-10: Checked against the tree and not fired. `residency_pass.py` still calls `fence()`
  synchronously and returns when it answers false, immediately before the one
  `await host.start(model)` in the module. The handoff is off unless `CORTEX_ESCALATION` is set,
  which no compose file here does.
- 2026-09-12: Checked against the supervisor and not fired, and the cost was corrected.
  `ModelSupervisor` holds one `asyncio.Lock` per roster id and takes it in all three verbs, which
  orders a start the daemon has begun serving against the stop that follows it, and orders nothing
  about which of two requests the daemon serves first. What the entry had wrong is the price of the
  second outcome: `swap_in` reads the card once, between its last eviction and the deep start, and
  `cadence.py` says that a handoff which overcommitted succeeds with both tiers reporting ready, so
  that outcome costs roughly half the deep model's decode rate rather than nothing.
  `residency_pass.py`'s module docstring was repaired at the same time, having presented the
  per-model lock as covering the in-flight start. Read against
  [R-200](200-placer-one-bit-per-card.md), they are not one defect seen twice: this is an ordering
  residue between two control calls on one loopback client, and that one is the width of a single
  boolean in `VramBudgetPlacer`.
- 2026-09-17: Checked again and not fired; no commit since 2026-09-12 touched
  `residency_pass.py`, `residency_moves.py` or the supervisor. The two outcomes each need a setting
  this entry had not named. The fit check returns at once while `plan.brain_vram_mib` is zero
  (`residency_moves.py`, `_refuse_a_load_the_card_cannot_hold`), and an overcommit result is `None`
  while the declared floor is zero (`cadence.py`, `below_floor`), so a deployment that sets neither
  figure cannot record either outcome. All four settings appear under `docker/` only in the comment
  block of `docker/docker-compose.gpu.yml`.
- 2026-09-24: Not fired. Since 2026-09-17 only renames touched `residency_pass.py`,
  `residency_moves.py` and the supervisor: `fence()` still answers immediately before the one
  `await host.start(model)`, and both zero-figure early returns hold. The four settings are now bare
  keys in the gpu overlay's brain environment, which the grep does not match, and no record in
  `docs/readings/` has a retry pass starting a peer during a handoff.
- 2026-10-03: Not fired, and the trigger rewritten to name the record that decides it, since it
  named an event and a grep of shipped settings that could not decide it. `fence()` still answers
  at `residency_pass.py:61`, immediately before the one `await host.start(model)` at line 64, and
  both zero-figure early returns hold (`residency_moves.py:66`, `cadence.py:33`). The agent now
  runs live handoffs on this machine, but the stacks of 2026-10-02
  (`measurements/sitting-2026-10-02b/drivers/stack.sh`) unset `CORTEX_SWAP_EVICT_MODELS`, so no
  retry pass could act during one, and the grep finds no record. The body had not named the
  co-resident case, where `swap_in` stops no peer (`residency_moves.py:42`) and the conductor
  skips the drain (`swap_conductor.py:187`).
