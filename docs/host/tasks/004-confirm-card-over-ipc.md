# The confirm card through real Tauri IPC

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

**What only this proves.** That the `ConfirmRoute` compare-and-clear and the `confirm_response`
command take an answer back into a live turn over the real IPC transport. The card itself was
validated in Chrome on 2026-07-08 (approve, deny, multi-turn) and the confirm exchange was proven
over a real loopback gRPC wire on both answers; neither reaches the Tauri IPC hop. The validation
plan in [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 6 states the same, and the
runbook for it is [body-overlay.md](../../runbooks/body-overlay.md).

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation step 4. Ask
for an action that needs approval (a send, with `CORTEX_EMAIL_SEND_ENABLED=true` and the Bridge
reachable, or any name you put in `CORTEX_TOOLS_GATED`). Approve. Repeat and deny. Repeat and
**ignore** it.

**Pass.** Approve runs the action and the turn continues. Deny returns the declined message and
nothing happens. Ignoring it denies on timeout (default 120 s) and the reply says the user
declined. A card arriving while the overlay is minimized shows the preview, and that preview does
**not** fade on its own while the question is open.

**Fail.** A card that appears and whose answer never reaches the brain is the IPC hop failing, the
exact thing this check exists for. A turn that proceeds *without* an answer would bypass the
approval and is the one failure here that is a security finding rather than a bug.

**Record it.** Edit [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) in place where it names
this as still pending and host-only; then delete this section.

## Notes

- The session doc numbers this check **3**, and ADRs cite it by that number.
- It needs a tool that requires approval to be enabled before the session starts, per the W
  prerequisites: either `CORTEX_EMAIL_SEND_ENABLED=true` with the Bridge reachable, or any tool
  name in `CORTEX_TOOLS_GATED`.
- The recommended order puts the confirm card and the toast together as the two consent surfaces
  the safety posture rests on, which is part of why this session is the one to start with.
- Its backlog line lived under the untrusted-content area rather than the email-confirmer one,
  which is worth knowing when searching for it.

## History

- 2026-07-19: moved here from the refinements backlog, where the Windows-native validation of the
  card had been a counted entry in the untrusted-content area. A dated pointer stays at the origin
  doc so the trail from an ADR through that backlog still resolves.
