# The load-failure note calls the hand-over sentence an answer

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-06

When the deep model cannot be loaded, the turn ends with `SWAP_FAILED_NOTE` from
`brain/packages/core/src/cortex_core/swap_notes.py`: "The usual assistant is back and the answer
above is what I have." `UNHOSTED_TIER_NOTE`, `STORE_FAILED_NOTE` and `DRAIN_TIMEOUT_NOTE` end the
same way. The text above is whatever the cortex wrote before it called `escalate_to_brain`, which
in the overlay run on 2026-10-06 was only "I am handing this task over to the deep model to
provide a concise, two-sentence explanation of why the sum of the first $n$ odd numbers equals
$n^2$." So the note tells the user that a sentence promising an answer is the answer
([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)).

**Do.** Write these notes so they are true whatever the cortex wrote first: say that the request
was not answered and that asking again, or in a new message, is the way on, and drop "the answer
above". Check the notes' tests and any runbook that quotes them.

## History

- 2026-10-06: filed by the overlay's view of a killed handoff on the Linux shell
  ([H-019](../../host/tasks/019-chaos-kill-tier-scale.md)).
