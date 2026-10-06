# The chaos kill at tier scale

**Status:** done 2026-10-06
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The kill and the hard-rule checks were drawn headless on 2026-10-02, and the overlay's view of a
killed handoff was run on the Linux shell on 2026-10-06: a kill at load and one at the first answer
text each ended the turn with its note and no wedged spinner, the dot green, and the next turn typed
in the same chat named the earlier request. Both readings are in
[the model swap readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff). Nothing in
that view is Windows code: the note is text in the bubble, the spinner and the dot are the overlay's
own state, and the answer travels the same Tauri command and gRPC client on both shells. What a
WebView2 renderer adds, painting while the deep model holds the card, is
[H-018](018-tier-scale-swap.md)'s, and a kill frees the card rather than filling it.

## History

- 2026-07-19: marked as needing both capabilities, after an audit tried to execute this item and its
  two siblings from the GPU doc alone. The kill itself is a `docker exec` on the card's machine;
  what the other capability supplies is the approved confirm card that puts a handoff in flight.
- 2026-08-04: the deep-model pick closed, which unblocked this item along with the swap, the timings
  and the injection-harness run, leaving the overlay as what still blocks it.
- 2026-10-02: re-scoped to the overlay's view of a killed handoff. The approved card that puts a
  handoff in flight can come from any client holding the `Converse` stream, so the kill and the
  hard-rule checks were drawn headless on the card that night with the handoff client, and the hard
  rule held ([readings](../../readings/model-swap.md#a-handoff-through-the-conductor)). What stays
  here is the overlay alone.
- 2026-10-06: done on the Linux shell, through `xdotool` clicks against the real stack on the card
  ([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)).
