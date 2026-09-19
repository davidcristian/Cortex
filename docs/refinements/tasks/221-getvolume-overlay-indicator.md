# `GetVolume` as an overlay volume indicator

**Status:** declined 2026-07-16
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Showing the system volume in the overlay, plus the remaining `BodyService` RPCs, `CaptureScreen` and
`InjectInput`, which the entry said were all behind the unchanged interfaces. Only the overlay half
is declined ([ADR-0023 decision 13](../../adr/ADR-0023-body-gateway-volume.md)).

Three findings settled it.

The entry names the wrong interface. `GetVolume` is a `BodyService` RPC and the body is its server,
and the overlay is inside the body, so it would never call that RPC. Showing volume there means a
new Tauri command over `AudioControl` plus a new overlay port, since `BrainBridge` is by definition
the overlay's port to the brain and a host-local fact does not belong on it.

Nothing would read it. No overlay control changes volume, none is designed, and ADR-0023 chose
volume precisely as a spoken, reversible action.

And it could not stay true. The connection dot works because a turn's own events refresh it for free
and a probe answers the exact question; volume changes from hardware keys and other apps with
nothing to tell the overlay, so a number read at summon is wrong seconds later, next to an OS tray
icon that is always right.

It reopens when the overlay gains a control that changes volume, or when a host-side change event
exists to push it (`IAudioEndpointVolumeCallback` is the producer that would make it a status rather
than a snapshot). Either way it is a new body-local port.

`CaptureScreen` closed on 2026-07-18 with the vision slice
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)), and the entry's "behind the same
interface" estimate was wrong: `proto/body.proto` gained five fields, `CaptureScreenRequest.max_edge`
and `max_bytes` plus `ImageBlob.source_width`, `source_height` and `captured_at_unix_ms`, and the
brain-side port grew a method returning a new pure-core value. Two of those were not in the design
either: `max_bytes` exists because a fixed byte ceiling made the shrink ladder's give-up branch
unreachable, and putting the budget on the request is what makes the brain's bound and the body's
ceiling one number rather than two constants tied together by prose.

`InjectInput` stays open and is the only unbuilt `BodyService` RPC.

## History

- 2026-07-16: Declined on the sharper of the two tests that day's other declines used: not only does
  nothing read it, nothing could keep it true. It also named the wrong interface, so the overlay
  would need a new body-local port rather than `BrainBridge`.
- 2026-07-16: Recorded beside the two other declines that the same want-of-a-producer test closed
  that day, a blended-relevance field on a recall hit and the per-error-code half of the
  rpc-transport retry entry.
- 2026-07-18: `CaptureScreen` closed with the vision slice, and the cost estimate proved wrong at
  five proto fields plus a new port method.
- 2026-07-19: Recorded at its origin ADR, which had gone on listing `CaptureScreen` as deferred in
  three places. The same pass gave `InjectInput` its own line in the index's
  dead-until-a-consumer list.
- 2026-08-07: Cited as the reference case when the subagents area declined a delegated tool step
  announced and never settled, on the sharper test that nothing could read the outcome rather than
  the usual want of a reader.
