# The tier-scale cortex to brain swap

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-07

Narrowed 2026-10-06 to what WebView2 does beside the deep model. The swap, its arithmetic and the
`Health` readings were drawn headless on 2026-10-02
([readings](../../readings/model-swap.md#a-handoff-through-the-conductor)), and the overlay's view
of a handoff was run on the Linux shell, whose overlay code, Tauri commands and gRPC client are the
ones the Windows shell runs: the card showed the tool's reason as written, a click on Approve
started the swap, the status lines arrived in order, the deep model's answer filled the bubble and
the cortex came back ([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)).
WebKitGTK drew that run on an `Xvfb` display where Mesa found no DRI3 device, so it drew without
the card.

**What only this proves.** That the panel keeps painting while the deep model holds the card. On
Windows, WebView2 draws with a GPU, and on a machine whose desktop and models share the 24 GB card
it competes with a deep phase that read 22304 of 24463 MiB used. Which adapter WebView2 picks on a
laptop with two GPUs is an assumption this file has not checked, so the first thing to read is the
GPU column of Task Manager's details for the WebView2 processes.

**Do.** With "Before you start" done **including step 10**, bring the overlay up beside the brain
([windows-desktop.md](../index.md#windows-desktop) has that bring-up), ask something that escalates,
approve the card, and watch the panel through the deep phase, which is while `GET /models/brain`
on the sidecar reads `ready`.

**Pass.** The panel keeps painting through the deep phase: the reasoning chip changes, the answer
streams in, and the header's buttons still answer a click.

**Fail.** A panel that stops painting, goes blank, or ignores input while the deep model is ready.
A swap or a restore that fails is a finding against the swap, not this one's:
[runbooks/model-swap.md](../../runbooks/model-swap.md) says how to read it.

**Record it.** In this file's History, and in the second readings section linked above wherever
WebView2 shows the window differently.

## History

- 2026-07-19: marked as needing both capabilities, after an audit tried to execute this item and its
  two dependents from the GPU doc alone. A handoff begins only at an approved confirm card, the only
  shipped client that answers one is the overlay, and the arithmetic needs the 24 GB card, so a
  session with one capability and not the other stalls at the card.
- 2026-07-19: the session's bring-up was run end to end on the dev machine, which settled how the
  escalation settings step 10 depends on have to be delivered. `CORTEX_ESCALATION`,
  `CORTEX_MODELHOST_BACKEND` and `CORTEX_BRAIN_ENDPOINT` are brain-side, and at the time no compose
  file passed them, so they had to go in the `brain` service's `environment:` block in
  `docker/docker-compose.gpu.yml` or in a local override. Supplying them in the calling shell left
  the container with none of them, and dropping `CORTEX_BRAIN_ENDPOINT` failed the brain at boot and
  restarted it forever. `CORTEX_MODELHOST_ENDPOINT` is already set by the GPU override.
- 2026-08-04: the deep-model pick closed, which unblocked this item along with the chaos kill, the
  timings and the injection-harness run, leaving the overlay as what still blocks this one.
- 2026-10-02: re-scoped to the overlay's view of a handoff. A probe of the code found that the
  confirm card is answered by any client holding the `Converse` stream and that the body's own
  client already sends a `ConfirmDecision`, so the swap, its arithmetic and the `Health` readings
  were drawn headless on the card that night with the handoff client, and passed
  ([readings](../../readings/model-swap.md#a-handoff-through-the-conductor)). What stays here is
  the overlay alone.
- 2026-10-06: narrowed to WebView2 painting beside the deep model. The overlay's view ran on the
  Linux shell against the real stack on the card, every click through `xdotool`, and passed what
  this file then asked except the dot: it stays green through the handoff's own turn by design,
  because each streamed event marks the brain as serving and a dismiss mid turn minimizes rather
  than hides, so nothing probes `Health` until the turn ends, after the cortex is back
  ([readings](../../readings/model-swap.md#the-overlays-view-of-a-handoff)). The run filed
  [R-794](../../refinements/tasks/794-a-paused-stream-keeps-its-last-letters-blurred.md).
