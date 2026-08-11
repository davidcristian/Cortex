# The connection indicator's real IPC hop

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

**Until 2026-07-19 this was recorded in one place only, a runbook paragraph.**

**What only this proves.** The `check_link` command across the real IPC hop. The classification
itself is gated in `body_core::link` and checked against a real brain by the `body-rpc` live suite,
so Windows adds the hop and nothing else.

**Do.** [runbooks/body-overlay.md](../../runbooks/body-overlay.md) section B, validation step 5.

**Pass.** Green on summon with the brain up. Stop the brain and summon: red within the retry budget,
staying red and re-checking every 5 s while the panel is open. Start the brain: green on its own,
without a re-summon, and the chat list fills in with it. Point at a live brain with the **wrong**
`CORTEX_SEAM_TOKEN`: amber, because the brain answered `Unauthenticated` and so is reachable and
refusing.

**Fail.** A dot that never leaves green is the honest-signal failure the ADR-0011 addendum was
written to avoid: an always-green dot is chrome that means nothing.

**Record it.** A dated addendum to [ADR-0011](../../adr/ADR-0011-body-v1.md); then delete this
section.

## Notes

- The sitting doc numbers this check **6**, and ADRs cite it by that number.
- The host index's roll call adds that it costs one brain stop and restart.
