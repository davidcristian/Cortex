# The `InjectInput` RPC, the last unbuilt `BodyService` RPC

**Status:** open, dead until a consumer
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)
**Trigger:** A real consumer for input injection, built then as one slice, not as a wired handler.
**Verified:** 2026-09-19

The remaining `BodyService` RPCs, `CaptureScreen` (Slice 10) and `InjectInput` (later), behind the
same seam. The remaining `BodyService` RPCs in this entry (`CaptureScreen`, `InjectInput`) stay open
with their slices; only the overlay half is declined. `InjectInput` stays open, and is now the only
unbuilt `BodyService` RPC, which is why the index **held this area at 6** on 2026-07-18 rather
than decrementing it: half an entry closing does not close the entry, and a count moved for a half-closed one is how
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
- 2026-09-13: Re-derived against all five tiers and every one still reads as the 2026-07-19 bullet
  recorded it. The RPC and its `TypeText`/`KeyChord` messages are still declarations only
  ([proto/body.proto](../../../proto/body.proto) lines 282 and 369 to 377); there is no input trait
  in `body_core` (`body/crates/core/src/os/` holds `notify` and the four screen modules and nothing
  else); `os_windows` has no input adapter; `body/crates/rpc/src/server.rs:121` still answers
  `Status::unimplemented`; and the brain's gateway
  (`brain/packages/body_client/src/cortex_body_client/gateway.py`) exposes `get_volume`,
  `set_volume`, `notify` and `capture_screen` and no inject method. It is still the only unbuilt
  RPC of the five `BodyService` declares. The trigger has not fired, since nothing asks to type or
  chord on the user's behalf. The entry stays a refinement rather than moving to
  [docs/host/](../../host/index.md): the proto field, the core trait, the gateway method, the fake
  and its contract test are all reachable and gated here, and only the real `SendInput` adapter and
  its validation need a Win32 desktop session, so moving the whole entry would hide the four fifths
  that do not.
- 2026-09-19: re-derived, and the 2026-09-13 reading still holds line for line.
  [proto/body.proto](../../../proto/body.proto) declares the RPC at line 282 and its messages at 369
  to 377; `body/crates/core/src/os/` holds `notify.rs` and the four `screen` modules, and
  `body/crates/core/src/os.rs` still says the input trait joins later; `os_windows` has no input
  module; `body/crates/rpc/src/server.rs:121` still answers `Status::unimplemented`; and the brain's
  gateway still exposes `get_volume`, `set_volume`, `notify` and `capture_screen`. No code under
  `body/`, `brain/` or `proto/` spells `SendInput`, and no tool or surface asks to type or chord, so
  the trigger has not fired. No circle: [270](270-pointer-input-injection.md) is declined, and the
  two feature-breadth entries that mention input injection ([271](271-macos-linux-os-backends.md),
  [272](272-more-subagent-roles.md)) wait on nothing here. The area reads 5 open entries today. The
  body's sentence about holding it at 6 was put in the past tense, since that count belonged to
  2026-07-18.
