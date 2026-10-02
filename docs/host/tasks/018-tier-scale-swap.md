# The tier-scale cortex to brain swap

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-10-02

Blocked on the overlay, for what the user sees and nothing else. Re-scoped 2026-10-02: the VRAM
arithmetic, the phases of the swap and the `Health` readings during the window are agent work on the
24 GB card through a client that approves the confirm card, the handoff client of
[a handoff without the overlay](../../runbooks/model-swap-measurements.md#a-handoff-without-the-overlay).
The approval is a `ConfirmResponse` on the `Converse` stream, which any client holding the stream
can send, and the body's own client already sends one, so the overlay was never the only way to
start a handoff. What stays here is the overlay's view of one. The headless swap rows drew on
2026-10-02: every approved handoff completed with the four details and returned the cortex
([readings](../../readings/model-swap.md#a-handoff-through-the-conductor)), and the deep model
answered once its context ended with a message addressed to it.

**What only this proves.** That the overlay shows a real handoff accurately: the
`escalate_to_brain` card with the tool's reason as written, the approval sent by a click, the
window's status lines (pausing delegated work, loading the deep model, the deep model working,
bringing the usual assistant back) shown in order over the minutes the swap takes, and the
connection dot amber while `Health` reads `ready=false` between turns, then green once the cortex
serves again.

**Do.** With "Before you start" done **including step 10**, bring the overlay up beside the brain
([windows-desktop.md](../index.md#windows-desktop) has that bring-up), then ask something that
escalates and **approve the card** when it appears. The headless swap rows have passed, so a failure
here is about the overlay and not about the swap. `GET /models/brain` on the sidecar flips
`stopped` to `loading` to `ready` while it runs, which tells an escalation that was never approved
from one that was.

**Pass.** The card shows the tool's reason, the approval starts the swap, each status line appears
when the stream sends it, the dot turns amber during the window and green after it, and the deep
model's answer appears in the panel.

**Fail.** A card that stays open after the approval, a status line that never appears, or a dot that
stays amber once the cortex is serving. A swap or a restore that fails is a finding against the
swap, not this one's: [runbooks/model-swap.md](../../runbooks/model-swap.md) says how to read it.

**Record it.** In this file's History, and in [runbooks/model-swap.md](../../runbooks/model-swap.md)
wherever the overlay shows the window differently from what that runbook says.

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
