# The deep reply is joined to the hand-over sentence

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-06

In a handoff the cortex writes a sentence saying it is handing the task over, calls
`escalate_to_brain`, and the deep model's reply then streams into the same bubble with nothing
between the two. In all four handoffs of the overlay run on 2026-10-06 the bubble read like
"equals $n^2$.Visually, adding each" and "the number zero.The number zero is"
([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)).

`SwapConductor._swap` in `brain/packages/core/src/cortex_core/swap_conductor.py` yields the loading
and working statuses and then every event of `BrainPhase.run` as it comes, so the first `TextDelta`
of the deep model follows the cortex's last one directly. The swap notes in `swap_notes.py` each
start with `"\n\n"`, which is the separator the deep reply lacks.

**Do.** Check first whether the session store keeps the cortex's sentence and the deep reply as one
message or two, since a reloaded chat shows what the store holds. Then give the live stream the
same break: either the conductor sends `"\n\n"` before the deep model's first text when the cortex
wrote any, or the overlay starts a new paragraph at the first text after a `swapping` status. A
fix in the brain also covers any other client of the `Converse` stream.

## History

- 2026-10-06: filed by the overlay's view of a handoff on the Linux shell, which saw it in every
  handoff ([H-018](../../host/tasks/018-tier-scale-swap.md)).
