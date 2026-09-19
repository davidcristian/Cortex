# body/crates/core: screen capture (`body_core::os::screen`)

**Purpose.** The screen-capture port and the pure size policy behind it (ADR-0029). It is the first
OS capability whose return value is a payload, and the port has **no policy**: a backend hands back
raw pixels plus the rectangle it resolved, and the pure core decides what crosses to the brain. The
per-platform backends are in [body-os.md](body-os.md) and the rest of this crate in
[body-core.md](body-core.md).

- `ScreenCapture` is the backend port:
  `capture(&self, &CaptureRequest) -> Result<CapturedFrame, CaptureError>`, `Send + Sync` and
  synchronous for the same reasons as `AudioControl`.
- `RawFrame::new(width, height, pixels)` is BGRA straight from the OS, four bytes per pixel,
  top-down. It rejects a zero dimension or a buffer that is not `width * height * 4` bytes. The
  fourth byte is deliberately unspecified, GDI leaving it undefined, and the encoder drops it.
- `CaptureTarget` mirrors the wire enum: `Display` (the whole primary display, the proto3 zero) or
  `Focus` (the topmost visible top-level window that is neither the body's own nor excluded from
  capture). It is a closed vocabulary the body resolves and never a rectangle the caller names,
  because a model that will not admit it cannot read a screen would invent one just as readily.
- `CapturedFrame::display(frame)` and `CapturedFrame::window(frame, TargetRect)` are what a backend
  answers: the **whole display's** pixels either way, plus where in them the target was.
  `TargetRect::new(left, top, right, bottom)` is signed and unvalidated, exactly as the OS reports
  it, since a window may hang off an edge or sit on another monitor. Clamping it into the frame, and
  rejecting one with nothing on the display (`CaptureError::NoTarget`), is the core's job.
- `CaptureRequest::targeted(max_edge, max_bytes, target)` resolves every proto3 hint: a zero edge
  becomes `DEFAULT_MAX_EDGE` (1600) and a zero ceiling becomes `MAX_CAPTURE_BYTES` (6 MiB,
  `6 * 1024 * 1024`); an edge above `MAX_EDGE_CEILING` (4096) and a ceiling above
  `MAX_CAPTURE_BYTES` are clamped down, so a caller can only tighten these bounds.
  `CaptureRequest::bounded(max_edge, max_bytes)` and `CaptureRequest::new(max_edge)` are the same
  for the whole display.
- `Capture::from_bgra(&CapturedFrame, &CaptureRequest)` is the whole policy: crop to the resolved
  region, downscale so the long edge is at most `max_edge`, PNG encode, and while the result is over
  `max_bytes` halve the edge **that was actually reached** and retry, up to `MAX_SHRINK_ATTEMPTS`
  (2) times, then answer `CaptureError::TooLarge(bytes)`. Checking the size after encoding is the
  only order that can work, since a flat desktop is kilobytes at 1600x900 and a photograph is
  megabytes. A `Capture` exposes `data`, `mime_type` (always `CAPTURE_MIME`, `image/png`), `width`
  and `height` after the crop and downscale, `source_width` and `source_height`, which are always
  the **display's** since three consumers read them as the size of the screen, and
  `covers_display()`, the one bit the receipt needs. **`TooLarge` is unreachable at this ceiling**,
  which is why the ceiling travels with the request: each step halves the edge the last one reached,
  so the third is at most a quarter of the requested edge and a 1024 px image cannot exceed 6 MiB.
  Only a caller naming a much tighter `max_bytes` reaches it, which is what the covered test for it
  does.
- `encode_png(width, height, rgb)` is the encoder, public so its two rejections (a zero dimension, a
  buffer that is not `width * height * 3` bytes) can be provoked by a caller. The downscaler is a
  box filter with a separate identity path, so a region already inside the bound crosses pixel for
  pixel; averaging rather than dropping pixels is what keeps thin strokes, which is to say text,
  legible after a shrink. That identity path is why a targeted capture is worth the extra wire
  field: measured through this code, a 1720x1200 window of a 4K wallpaper desktop costs 43450 B
  untouched where the same desktop whole costs 1978393 B resampled to 2048 px.
- `CaptureError` (thiserror, `Clone`) is `NoDisplay(String)`, `Disabled`, `Backend(String)`,
  `NoTarget(String)` or `TooLarge(usize)`. `DeniedScreenCapture` is the unit backend that always
  answers `Disabled`; it is real covered code on every platform rather than a stub, because a host
  that switched capture off has to keep answering no under test.
- `CAPTURE_RECEIPT_TITLE`, `CAPTURE_RECEIPT_BODY_DISPLAY`, `CAPTURE_RECEIPT_BODY_WINDOW` and
  `CAPTURE_RECEIPT_ID` are the fixed, body-owned strings of the notification a successful capture
  shows, the two bodies being a picture of the screen and a picture of one window. They live here
  beside `UNTRUSTED_ATTRIBUTION` for the same reason: the notice that tells the user their screen
  was read may never be built from anything the brain sent. Neither names the window, a title being
  attacker-chosen text.
- `tests/capture_bytes.rs` measures how much room the ceiling leaves at the 2048 px edge the brain
  asks for. It is `#[ignore]`d, being seconds of CPU rather than part of the check. It names that
  edge as `BRAIN_EDGE`, and `scripts/crosscheck.py` compares it with the brain's own
  `DEFAULT_CAPTURE_MAX_EDGE`, since an edge retuned on the brain alone would leave the headroom
  reported here measured for a capture nothing asks for (ADR-0042). The baseline printed beside it,
  `BODY_EDGE`, is `DEFAULT_MAX_EDGE` imported, so the compiler holds that one. The costliest display
  there is 2560x1440 rather than 4K, at 79% of the ceiling under heavy grain, because a display
  nearer the requested edge averages less of the grain away.

