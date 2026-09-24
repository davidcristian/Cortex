# The retry pass's start guarded but not ordered

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Trigger:** A handoff refused at its fit check, or recorded as having overcommitted, with a peer a
retry pass had just started. Either needs a live handoff, which is off-tree, and four settings that
all default off: `CORTEX_ESCALATION`, a non-empty `CORTEX_SWAP_EVICT_MODELS`, and
`CORTEX_SWAP_BRAIN_VRAM_MIB` (the refusal case) or `CORTEX_SWAP_BRAIN_DECODE_TPS` (the overcommit
case). The gpu overlay passes all four through by name, so a host `.env` can set them, and
`grep -rnE '(CORTEX_ESCALATION|CORTEX_SWAP_EVICT_MODELS|CORTEX_SWAP_BRAIN_VRAM_MIB|CORTEX_SWAP_BRAIN_DECODE_TPS): *[^ ]' docker/`
finding nothing means no shipped file sets any of them.
**Verified:** 2026-09-24

A retry pass reads the handoff claim and the residency scope flag synchronously in the instant
before it starts a tier, so a handoff cannot begin between the check and the call. What is not
excluded is the other order: a `start` already sent when a handoff begins, whose request the daemon
serves after the swap in's own `stop` of that same tier, leaving a peer loading beside the deep
model. Reaching it means one loopback request outliving the claim, the whole drain, the lease wait,
a `boot_id` round trip and a full cortex stop, so it is narrow.

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
