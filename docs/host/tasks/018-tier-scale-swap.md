# The tier-scale cortex to brain swap

**Status:** never attempted
**Sitting:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Blocked on item 1. Tag **W+G**, corrected 2026-07-19: this item sat under G alone, and both its
procedure and its pass line need the Windows overlay.

**What only this proves.** The VRAM arithmetic. The agent's validation ran two small artifacts
through every code path, which is explicitly not the same thing: evicting ~11.3 GB and loading 15
to 18 GB alone is the part that was never exercised.

**Why it needs the overlay too, and cannot be done headless today.** `escalate_to_brain` carries
`gated=True` in its own spec (`brain/packages/core/src/cortex_core/escalate.py`), so a handoff
begins only after the ADR-0022 confirm card is **approved**. That card is not a brain-side prompt:
the brain emits a `ConfirmRequest` on the Converse stream and waits
`CORTEX_SEAM_CONFIRM_TIMEOUT_S` (120 s) for the client's `ConfirmResponse`, and an unanswered one
is denied fail-closed, so nothing swaps. The only shipped client that answers a `ConfirmRequest` is
the overlay (`body/crates/rpc/src/converse.rs`, `body/app/src/bridge/tauriBridge.ts`); the repo's
own headless Converse driver, `just seam-health`, opens a stream, reads it, and answers no confirm.
So the trigger and the amber dot are the overlay's, and the arithmetic is the card's. Nothing about
this makes it a Windows item: no overlay can evict 11.3 GB and load 18 GB. If the Windows desktop
and the 24 GB card are the same laptop, this costs one bring-up of each side and nothing more.

**Do.** With "Before you start" done **including step 10**, bring the overlay up beside the brain
([windows-desktop.md](../index.md#windows-desktop) has that bring-up), then ask something that escalates and
**approve the card** when it appears. Watch the swap window's `StatusUpdate`s. To see the swap from
the other side while it runs, `GET /models/brain` on the sidecar (step 6's command) flips
`stopped` to `loading` to `ready` and the cortex flips the other way; that is also how you tell an
escalation that was never approved from one that was.

**Pass.** The cortex is evicted, the deep model loads, the answer returns, and the cortex is
restored. `Health` reads `ready=false` with a truthful residency detail between turns during the
window, which lights the overlay's connection dot amber.

**Fail.** A load that never completes inside `CORTEX_SWAP_LOAD_TIMEOUT_S` is item 4's problem,
not this one. The failure that matters here is a restore that does not happen:

```
could not restore '<cortex model>' after 2 attempts, the last of which failed on '<tier>';
manual recovery is needed
```

which is `ResidencyRestoreError`, and [runbooks/model-swap.md](../../runbooks/model-swap.md) has the
section on what to do about it.

**Record it.** A dated addendum to [ADR-0030](../../adr/ADR-0030-brain-handoff.md) and the tier-scale
half of [runbooks/model-swap.md](../../runbooks/model-swap.md).

## Trail

- 2026-07-19: Marked as needing both capabilities, after an audit tried to execute this item and its
  two dependents from the GPU doc alone. The index states what the marking buys: a handoff begins
  only at an approved confirm card, the only shipped client that answers one is the overlay, and the
  arithmetic this item exists to prove needs the 24 GB card, so a sitting that has one capability
  and not the other stalls at the card.
- 2026-07-19: The sitting's bring-up was run end to end on the dev machine, which settled how the
  escalation settings this item's step 10 depends on have to be delivered. `CORTEX_ESCALATION`,
  `CORTEX_MODELHOST_BACKEND` and `CORTEX_BRAIN_ENDPOINT` are brain-side and no compose file
  interpolates them, so they belong in the `brain` service's `environment:` block in
  `docker/docker-compose.gpu.yml` or in a local override layered after it. Supplying them in the
  calling shell was confirmed to leave the container with none of them, and dropping
  `CORTEX_BRAIN_ENDPOINT` was confirmed to fail the brain at boot and restart it forever.
  `CORTEX_MODELHOST_ENDPOINT` is already set by the GPU override and is not added.
- 2026-08-04: The deep-model pick closed, and the index recorded it as unblocking this item along
  with the chaos kill, the timings and the injection-harness run, leaving the overlay as what still
  holds this one. The body above still names item 1 as the blocker, which is the older reading of
  the same dependency.
