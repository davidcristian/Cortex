# Unbalanced COM initialization on the blocking pool

**Status:** standing: an observation to make over months of real use, never a check that passes
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Not a check to run. Both Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per call and
never `CoUninitialize`, which on tokio's blocking pool means threads join the MTA and are later
reaped unbalanced. Only a long-uptime Windows session with sporadic OS actions can show it.

The fix and the argument for it stay in
[refinements/body-gateway.md](../../refinements/index.md#body-gateway), which is where the code cost
belongs; what lives here is the trigger, kept verbatim from that entry:

> **Fix when it bites**, the trigger being any COM failure or thread growth the user sees on
> Windows after a long session

**Watch for.** A volume or toast call that starts failing after the app has been up for a long
time, or Tauri's thread count growing without bound.

**Record it.** If it ever bites, say so on that refinements entry, which then becomes actionable.

## Notes

- The host index's recommended order lists neither this item nor the toolchain-linked full build,
  and its roll call carries the two of them under a heading of their own rather than with the
  numbered checks.
- The refinements entry it points at was opened 2026-07-16 behind the landed `spawn_blocking`, and
  the code cost stays counted there rather than here.
