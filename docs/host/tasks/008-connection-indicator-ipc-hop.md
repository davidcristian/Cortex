# The connection indicator's real IPC hop

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**What only this proves.** The `check_link` command across the real IPC hop. The classification
itself is covered in `body_core::link` and checked against a real brain by the `body-rpc` live
suite, so Windows adds the hop and nothing else.

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation step 5.

**Pass.** Green on summon with the brain up. Stop the brain and summon: red within the retry
budget, staying red and re-checking every 5 s while the panel is open. Start the brain: green on
its own, without a re-summon, and the chat list fills in with it. Point at a live brain with the
**wrong** `CORTEX_SEAM_TOKEN`: amber, because the brain answered `Unauthenticated` and so is
reachable and rejecting the token.

**Fail.** A dot that never leaves green is the failure ADR-0011 decision 8 was written to avoid: an
always-green dot means nothing.

**Record it.** Edit [ADR-0011](../../adr/ADR-0011-body-v1.md) in place where the run changes what it
states; then delete this section.

## Notes

- The session doc numbers this check **6**, and ADRs cite it by that number.
- It costs one brain stop and restart.
- Until 2026-07-19 it was recorded in one place only, a runbook paragraph.
