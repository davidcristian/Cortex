# `GetVolume` as an overlay volume indicator

**Status:** declined 2026-07-16
**Area:** body-gateway
**Origin:** [ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)

Body gateway & OS actions in Slice 9 ([ADR-0023](../../adr/ADR-0023-body-gateway-volume.md)): each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.

`GetVolume` surfaced as overlay state (a real volume indicator), and the remaining
`BodyService` RPCs, `CaptureScreen` (Slice 10) and `InjectInput` (later), behind the same seam.
(The "same seam" half of this line is wrong for `CaptureScreen`; see the dated closure below.)

The reasons are no consumer and no refresh story ([ADR-0023
addendum](../../adr/ADR-0023-body-gateway-volume.md)). The remaining `BodyService` RPCs in this
entry (`CaptureScreen`, `InjectInput`) stay open with their slices; only the overlay half is
declined. **`CaptureScreen` closed 2026-07-18 with the vision slice
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)), and the entry's own cost estimate was
wrong in the way this index warns about:** it promised the remaining RPCs "behind the same seam",
and the seam changed. `proto/body.proto` gained five fields, `CaptureScreenRequest. max_edge` and
`max_bytes` plus `ImageBlob.source_width`, `source_height` and `captured_at_unix_ms`, and the
brain-side port grew a method returning a new pure-core value. Two of those were not in the design
either: `max_bytes` exists because a fixed byte ceiling made the shrink ladder's give-up arm
unreachable, and putting the budget on the request is what makes the brain's bound and the body's
ceiling one number rather than two constants coupled by prose. `InjectInput` stays open, and is now
the only unbuilt `BodyService` RPC, which is why the index **holds this area at 6** rather than
decrementing it: half an entry closing does not close the entry, and a count moved for a half-closed
one is how an open deferral gets lost.
**That 6 is this sentence's own moment, 2026-07-18, and the area has read 5 since the next day**,
when the host-Windows validation above moved to [docs/host/](../../host/index.md) and took its name
off the count. Corrected 2026-08-10 by a pass reading every entry against both counts: the rule the
sentence states is untouched, and only the number it happened to be illustrating had moved on.
**Recorded at its origin ADR on 2026-07-19, closing a two-of-three gap ([ADR-0023 capture-closure
addendum](../../adr/ADR-0023-body-gateway-volume.md)).** The closure and the wrong cost claim had
been written here and on the index while ADR-0023 still listed `CaptureScreen` as deferred to its
slice in three separate paragraphs, which is the ADR a reader of that deferral reaches first. The
same pass gave `InjectInput` its own line in the index's dead-until-a-consumer bucket, where it had
been counted since the extraction but never placed. Three findings, in the order that settled it.
**The entry names the wrong seam.** `GetVolume` is a `BodyService` RPC, and the body is its
*server*: the overlay is inside the body, so it would never call that RPC. Surfacing volume there
means a new Tauri command over `AudioControl` plus a new overlay port, since `BrainBridge` is by its
own definition the overlay's port *to the brain* and a host-local fact does not belong on it. So
"behind the unchanged seams" is false for this half.
**Nothing would read it.** No overlay affordance changes volume, none is designed, and ADR-0023
chose volume precisely as a spoken, reversible action.
**And it could not stay true.** The summon-edge latch that keeps the connection dot accurate works
there because a turn's own events refresh it for free and a probe answers the exact question; volume
changes from hardware keys and other apps with nothing to tell the overlay, so a number latched at
summon is wrong seconds later, next to an OS tray icon that is always right. That is the
always-green dot ADR-0011 removed in 2026-07-03, in another form, an indicator whose value nothing
keeps current.
**Reopens** when the overlay gains a control that *changes* volume (the number then has a job and a
reason to be fresh), or when a host-side change event exists to push it
(`IAudioEndpointVolumeCallback` is the producer that would make it a status rather than a snapshot).
Either way it is a new body-local port, not this entry's "unchanged seam".

## Trail

- 2026-07-16: Declined on the sharper of the two tests that day's other declines used: not only
  does nothing read it, nothing could keep it true, since volume changes with nothing to tell the
  overlay. It also named the wrong seam, `GetVolume` being an RPC the body serves, so the overlay
  would need a new body-local port rather than `BrainBridge`. The area count held at 6, its
  two-part first entry closing as two different outcomes on one day.
- 2026-07-16: The index recorded this decline beside the two others that the same want-of-a-producer
  test closed that day, a distinct blended-relevance field on a recall hit and the per-error-code
  half of the seam-transport retry entry.
- 2026-07-18: `CaptureScreen` closed with the vision slice
  ([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)), and the entry's own "behind the same
  seam" cost claim proved wrong at five proto fields plus a new port method. No count moved,
  `InjectInput` still being the unbuilt half of the entry.
- 2026-07-19: Recorded at its origin ADR by a dated capture-closure addendum, the same
  two-of-three species the ADR-0012 host-half miss was caught for, since ADR-0023 had gone on
  listing `CaptureScreen` as deferred in three places. The same pass gave `InjectInput` its own
  line in the index's dead-until-a-consumer bucket. Later that day the area went 6 to 5 when
  host-side work was extracted to [docs/host/](../../host/index.md).
- 2026-08-07: Cited as the reference case when the subagents area declined a delegated tool step
  announced and never settled: the index placed that decline on this entry's side of the line, the
  sharper test that nothing could read the outcome rather than the usual want of a reader that
  leaves a thing merely unbuilt.
- 2026-08-10: A pass reading every entry against both counts corrected the illustration inside
  this entry: the rule it states is untouched, and only the number it happened to use had moved on.
