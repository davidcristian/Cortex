# The confirm card through real Tauri IPC

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

**What only this proves.** That the `ConfirmRoute` compare-and-clear and the `confirm_response`
command carry an answer back into a **live** turn over the real IPC transport. The card itself was
validated in Chrome on 2026-07-08 (approve, deny, multi-turn) and the confirm exchange was proven
over a real loopback gRPC wire on both answers; neither reaches the Tauri IPC hop.

The ROADMAP said this in a slice status that was slimmed away on 2026-07-19; the wording that is
still live is [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)'s 2026-07-08 addendum:

> **Still pending (genuinely OS-native, host-only):** the **Windows Tauri confirm-card**
> validation (hotkey → gated send → card → approve/deny through the real IPC transport). It is the
> one piece Chrome/Docker can't reach, exactly as ADR-0013 predicted.

The runbook for it is [body-overlay.md](../../runbooks/body-overlay.md). The same obligation is
stated once more in [refinements/untrusted-content.md](../../refinements/index.md#untrusted-content):

> Only the Windows-native validation of the card remains host-side.

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation step 4. Ask
for a gated action (a send, with `CORTEX_EMAIL_SEND_ENABLED=true` and the Bridge reachable, or any
name you put in `CORTEX_TOOLS_GATED`). Approve. Repeat and deny. Repeat and **ignore** it.

**Pass.** Approve runs the action and the turn continues. Deny returns the declined message and
nothing happens. Ignoring it denies on timeout (default 120 s) and the reply says the user
declined. A card arriving while the overlay is minimized surfaces the preview, and that preview
does **not** auto-fade while the question is open.

**Fail.** A card that appears and whose answer never reaches the brain is the IPC hop failing, the
exact thing this check exists for. A turn that proceeds *without* an answer would be a gate bypass
and is the one failure here that is a security finding rather than a bug.

**Record it.** A dated addendum to [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md), whose
"Still pending (genuinely OS-native, host-only)" paragraph names exactly this; then delete this
section.

**Note on where this is recorded.** It originates at ADR-0022 but its backlog line lived under
[refinements/untrusted-content.md](../../refinements/index.md#untrusted-content) rather than
`email-confirmer.md`, which is worth knowing when searching for it.

## Notes

- The sitting doc numbers this check **3**, and ADRs cite it by that number.
- The host index's roll call adds that it needs a gated tool armed before the sitting starts, per
  the W prerequisites: either `CORTEX_EMAIL_SEND_ENABLED=true` with the Bridge reachable (the
  user's `netsh` portproxy), or any tool name in `CORTEX_TOOLS_GATED`.
- The recommended order puts the confirm card and the toast together as the two consent surfaces
  the safety posture rests on, which is part of why this sitting is the one to start with.

## Trail

- 2026-07-19: arrived in the host directory from the refinements backlog, where the Windows-native
  validation of the card had been a counted entry in the untrusted-content area. The refinements
  index listed it among the work that left for [docs/host/](../index.md) that day with the wording
  kept verbatim, and a dated pointer stub stayed at the origin doc so the trail from an ADR through
  that backlog still resolves.
