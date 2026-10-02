# Measured swap timings

**Status:** declined 2026-10-02
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Declined as host work: nothing in it needs the overlay. These are the phases of a real handoff
(drain, evict, load, work, restore), timed against the shipped 300 s `CORTEX_SWAP_LOAD_TIMEOUT_S`,
and a handoff starts at any client that approves the confirm card, not only at the overlay. The
brain sends each phase as a `swapping` status on the `Converse` stream, so a headless client reads
them as well as the panel does. The phases were drawn headless on 2026-10-02 with the handoff client
of [a handoff without the overlay](../../runbooks/model-swap-measurements.md#a-handoff-without-the-overlay),
and are in [model swap](../../readings/model-swap.md#a-handoff-through-the-conductor) beside the
control-API figures from 2026-08-07 they are compared against.

## History

- 2026-07-19: marked as needing both capabilities with the swap and the chaos kill, after an audit
  tried to execute the three of them from the GPU doc alone. The marking is inherited here, these
  being the phases of the swap rather than a run of their own.
- 2026-08-04: the deep-model pick closed and produced the figure this item's load phase is compared
  against, the deep tier loading cold in 99.6 s, which leaves the shipped 300 s
  `CORTEX_SWAP_LOAD_TIMEOUT_S` about two thirds unspent. That close unblocked this item along with
  the swap and the chaos kill, leaving the overlay as what still blocks it.
- 2026-10-02: declined, and the phases drawn headless on the card that night. The only reason it was host work was the confirm card, which any client holding the `Converse`
  stream can answer. The runbook instruction it pointed at now survives only as "record the
  timings here" in the chaos kill section of
  [model-swap-recovery.md](../../runbooks/model-swap-recovery.md); the readings record is where the
  timings go.
