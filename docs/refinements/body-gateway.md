# Body gateway & OS actions

These deferrals originate at [ADR-0023](../adr/ADR-0023-body-gateway-volume.md), which established the body gateway and its first OS action (volume) across the brain→body seam. Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** Host-Windows volume validation, body-initiated-stream tunnel fallback, hardened non-loopback posture, spawn_blocking for the sync OS call, GetVolume overlay state and remaining BodyService RPCs, safe Core Audio wrapper

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
- **A safe Core Audio wrapper.** `WindowsAudioControl` uses the ADR-0023-scoped `unsafe` over the
  `windows` crate's COM API; a fully-safe wrapper crate (à la `global-hotkey` for the hotkey) would
  retire the exception if one matures.
