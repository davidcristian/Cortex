# Body gateway & OS actions

These deferrals originate at [ADR-0023](../adr/ADR-0023-body-gateway-volume.md), which established the body gateway and its first OS action (volume) across the brain→body seam. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** Host-Windows volume validation, body-initiated-stream tunnel fallback, hardened non-loopback posture, remaining BodyService RPCs, safe Core Audio wrapper, unbalanced COM initialization on the blocking pool

**Body gateway & OS actions in Slice 9 ([ADR-0023](../adr/ADR-0023-body-gateway-volume.md)):** each
behind the unchanged `BodyGateway`/`AudioControl`/`BodyService` seams.
- **Host-Windows validation.** The CI-gated half and the **agent-Docker dial are done**
  (2026-07-08, [ADR-0023 addendum](../adr/ADR-0023-body-gateway-volume.md), where a tokened round-trip
  passed across the container boundary, untokened rejected); the real Core Audio
  "set volume to 30%" on Windows remains. See [body-volume.md](../runbooks/body-volume.md).
- **The Q3 body-initiated-stream tunnel fallback.** The brain dials the body directly today; if
  `host.docker.internal` proves brittle on WSL2, tunneling body-directed calls over a
  body-initiated bidi stream is a different `BodyGateway` adapter, with no core/tool/proto change.
- **A hardened non-loopback posture.** The body binds a configurable interface (loopback for dev,
  `0.0.0.0` for the container→host path) behind the seam token + host firewall (assumption 5's
  revisit). mTLS / per-direction tokens, if the machine ever leaves single-user.
- **`spawn_blocking` for the sync OS call.** The `AudioControl` port is sync and called inline in
  the async `BodyService` handler (fine at personal scale, as it is a fast COM call); moving it to
  `spawn_blocking` is a body-side tweak behind the unchanged trait.
- **`GetVolume` surfaced as overlay state** (a real volume indicator), and the remaining
  `BodyService` RPCs, `CaptureScreen` (Slice 10) and `InjectInput` (later), behind the same seam.
  (The "same seam" half of this line is wrong for `CaptureScreen`; see the dated closure below.)
- **A safe Core Audio wrapper.** `WindowsAudioControl` uses the ADR-0023-scoped `unsafe` over the
  `windows` crate's COM API; a fully-safe wrapper crate (à la `global-hotkey` for the hotkey) would
  retire the exception if one matures.
- **`spawn_blocking` for the sync OS calls landed 2026-07-16 ([ADR-0023
  addendum](../adr/ADR-0023-body-gateway-volume.md)), and now covers three calls rather than
  one.** The entry was accurate: the ports really are sync, the handlers really did call them
  inline, and nothing about the seam had to move. Two things it could not have known. **The
  reminder toast joined the same shape**, so `off_worker` in `body_rpc::server` serves
  `get_volume`, `set_volume`, and `notify`; the toast is the slower of the two backends, since
  activating a WinRT factory and asking `ToastNotifier.Setting` both cross to the notification
  service. And **the entry's own "fine at personal scale" was the weaker half of the case**:
  the cost is not the COM call's latency, it is that `BodyService` shares its runtime with the
  overlay's own seam calls, so a parked worker delays work that has nothing to do with audio.
  **The safety question the change turns on was checked before it was made**, because a
  `spawn_blocking` that moves a `!Send` COM object to another thread is a bug and not a fix:
  neither backend holds one. `WindowsAudioControl` is a unit struct that resolves its
  `IAudioEndpointVolume` per call, `WindowsNotify` holds only an app-id `String`, and both
  ports were already `Send + Sync`, so the whole COM lifetime stays inside one closure on one
  thread. The backends move behind an `Arc` in `OsService` purely to be lent to that thread.
  **One behaviour changed, for the better:** a backend that panics mid-call used to kill the
  connection (the brain sees `Cancelled`); it now answers `Internal` like any other backend
  fault, which the contract tests assert over a channel that is still usable afterwards. Proven
  rather than assumed: the fakes record which thread each call ran on, and a current-thread test
  runtime makes an inline call observable (reverting `off_worker` turns three tests red).
  Validated live as well, with the brain's own `GrpcBodyGateway` dialling the real Rust server
  over loopback: tokened round-trip passed, untokened still `UNAUTHENTICATED`, and the server
  log shows all three OS calls on a blocking-pool thread.
- **`GetVolume` as an overlay volume indicator closed 2026-07-16 as declined, no consumer and no
  refresh story ([ADR-0023 addendum](../adr/ADR-0023-body-gateway-volume.md)).** The remaining
  `BodyService` RPCs in this entry (`CaptureScreen`, `InjectInput`) stay open with their slices;
  only the overlay half is declined. **`CaptureScreen` closed 2026-07-18 with the vision slice
  ([ADR-0029](../adr/ADR-0029-vision-screen-capture.md)), and the entry's own cost estimate was
  wrong in the way this index warns about:** it promised the remaining RPCs "behind the same
  seam", and the seam changed. `proto/body.proto` gained five fields, `CaptureScreenRequest.
  max_edge` and `max_bytes` plus `ImageBlob.source_width`, `source_height` and
  `captured_at_unix_ms`, and the brain-side port grew a method returning a new pure-core value.
  Two of those were not in the design either: `max_bytes` exists because a fixed byte ceiling made
  the shrink ladder's give-up arm unreachable, and putting the budget on the request is what makes
  the brain's bound and the body's ceiling one number rather than two constants coupled by prose.
  `InjectInput` stays open, and is now the only unbuilt `BodyService` RPC. Three findings, in the order they killed it. **The entry
  names the wrong seam.** `GetVolume` is a `BodyService` RPC, and the body is its *server*: the
  overlay is inside the body, so it would never call that RPC. Surfacing volume there means a
  new Tauri command over `AudioControl` plus a new overlay port, since `BrainBridge` is by its
  own definition the overlay's port *to the brain* and a host-local fact does not belong on it.
  So "behind the unchanged seams" is false for this half. **Nothing would read it.** No overlay
  affordance changes volume, none is designed, and ADR-0023 chose volume precisely as a spoken,
  reversible action. **And it could not stay true.** The summon-edge latch that keeps the
  connection dot honest works there because a turn's own events refresh it for free and a probe
  answers the exact question; volume changes from hardware keys and other apps with nothing to
  tell the overlay, so a number latched at summon is wrong seconds later, next to an OS tray
  icon that is always right. That is the always-green dot ADR-0011 removed in 2026-07-03, in
  another form: chrome earns its place by meaning something. **Reopens** when the overlay gains
  a control that *changes* volume (the number then has a job and a reason to be fresh), or when
  a host-side change event exists to push it (`IAudioEndpointVolumeCallback` is the producer
  that would make it a status rather than a snapshot). Either way it is a new body-local port,
  not this entry's "unchanged seam".
- **Unbalanced COM initialization on the blocking pool (opened 2026-07-16 behind the landed
  `spawn_blocking`).** Both Windows backends call `CoInitializeEx(COINIT_MULTITHREADED)` per
  call and never `CoUninitialize`. That was already true on the async workers, where the thread
  set is small and lives as long as the process; on the blocking pool it applies to threads
  tokio creates on demand and reaps after an idle timeout, so a long uptime with sporadic OS
  actions joins the MTA from many threads that then exit unbalanced. Harmless as far as anything
  observed goes, and arguably what a resident body wants (the apartment stays up), but it is
  documented as incorrect and it is now the shape of the code. **Fix when it bites**, the
  trigger being any COM failure or thread growth the user sees on Windows after a long
  session: funnel the OS calls through one dedicated COM-initialized thread instead, which
  also amortizes the initialization. Uninitializing at the end of each call is the wrong fix,
  since it would tear down and rebuild MTA membership per call. Host-Windows to observe;
  neither CI nor a Linux run can see it.
