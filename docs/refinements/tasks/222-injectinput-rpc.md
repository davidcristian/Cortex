# The `InjectInput` RPC, the last unbuilt `BodyService` RPC

**Status:** open, dead until a consumer
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A real consumer for input injection, built then as one slice, not as a wired handler.

The remaining `BodyService` RPCs, `CaptureScreen` (Slice 10) and `InjectInput` (later), behind the
same seam. The remaining `BodyService` RPCs in this entry (`CaptureScreen`, `InjectInput`) stay open
with their slices; only the overlay half is declined. `InjectInput` stays open, and is now the only
unbuilt `BodyService` RPC, which is why the index **holds this area at 6** rather than decrementing
it: half an entry closing does not close the entry, and a count moved for a half-closed one is how
an open deferral gets lost.

Those fragments were recorded inside the `GetVolume` surfaced as overlay state entry, which grouped
the overlay indicator with the remaining `BodyService` RPCs and never gave `InjectInput` a bullet of
its own.

## Trail

- 2026-07-18: `CaptureScreen` closed with the vision slice
  ([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)), which is what leaves `InjectInput` alone
  in the entry and why the area held at 6 rather than decrementing. On that half the entry's own
  "behind the same seam" cost claim proved wrong, at five proto fields plus a new brain-side port
  method returning a new pure-core value.
- 2026-07-19: Given its own line in the index's dead-until-a-consumer bucket, where it had been
  counted since the extraction but never placed, surfacing until then only inside the pointer-input
  decline. Same blocker and same shape as that decline: input injection is unbuilt at every tier
  (the `InjectInput` RPC and its `TypeText`/`KeyChord` messages are Slice 2 forward-looking stubs,
  there is no `body_core` input trait, no `os_windows` adapter, the body server answers
  `inject_input` with `Status::unimplemented`, the brain's `BodyGateway` carries no inject method,
  and no tool drives it), so the RPC reopens with its consumer as one slice rather than as a wired
  handler waiting for the gated tool that would make it safe. Later that day the area went 6 to 5
  when host-side work was extracted to [docs/host/](../../host/index.md).
- 2026-08-03: The index named this area's hold as the precedent for the vision area's own, when the
  `opaque` bit's half of the pixels-across-a-swap entry landed and the picture half did not: a cell
  decremented for a half-closed entry is how an open deferral gets lost, which is the rule the hold
  on this half established.
- 2026-08-10: A pass reading every entry against both counts dated the 6 quoted above to its own
  moment, 2026-07-18, and recorded that the area has read 5 since the next day, when the
  host-Windows validation moved to [docs/host/](../../host/index.md) and took its name off the count.
  The rule the sentence states is untouched, and only the number it happened to be illustrating had
  moved on.
