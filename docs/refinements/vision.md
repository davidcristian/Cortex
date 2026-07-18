# Vision (screen capture, images, and the pixel boundary)

This area originates in [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) (Slice 10), which
gave the cortex eyes: a model-initiated `capture_screen` built-in over the brain→body seam, all
downscale/encode/byte-bounding policy in pure `body_core`, a GDI Windows backend, and pixels
treated as untrusted and unfenceable content. Recorded when the slice landed on 2026-07-18; the
index at [index.md](index.md) carries the recommended pickup order.

**Open items:** the user-attached image path, region and window capture, legibility at 4K, a
cross-language check on the byte ceiling, a live-probe refresh, JPEG or WebP for photographic
screens, an `AttachmentStore` for accountability, an image arm of the injection harness,
per-source memory rules, a Windows.Graphics.Capture backend, multi-monitor and DPI reporting,
Linux and macOS backends, a uniform per-call deadline, `RESOURCE_EXHAUSTED` classification, and
pixel screening in the body.

## Vision in Slice 10 ([ADR-0029](../adr/ADR-0029-vision-screen-capture.md))

- **The user-attached image path** (`UserTurn.images`). The proto field has existed since Slice 2
  and is still ignored. It is a genuinely different design, not a smaller version of this one: a
  different seam direction, a different transport limit in a different package, the first path
  where Cortex would **decode a foreign image**, a four-layer TypeScript bridge change, and a
  persistence answer the capture path deliberately refused to give (pixels here are turn-local).
  It lands with its own design, and the in-code notes that used to promise it "arrives with
  vision" now point here instead.
- **Region and window capture, and legibility at 4K.** The headline risk. The projector tiles to
  a bounded token budget (measured: 266 tokens for anything from 720p up), so a 4K desktop
  downscaled to 1600 px may render small text unreadable. Expect layout-level answers to be good
  and small-text answers unreliable. The **first** mitigation is a deployment flag with no code
  at all, llama.cpp's `--image-max-tokens`; the real fix is capturing a region or a window rather
  than a bigger PNG, which needs the `display_index`/`region` proto fields ADR-0029 deliberately
  refused to add without a consumer. The `CaptureRequest` value already carries the shape.
- **A cross-language check on the byte ceiling.** `MAX_CAPTURE_BYTES` (Rust) and
  `MAX_IMAGE_BYTES` (Python) are the same number, 6 MiB, and each is pinned to the literal
  `6291456` by a test in its own toolchain. **Nothing mechanical couples them**: an edit to one
  leaves both suites green. The wire's `max_bytes` hint removes most of the risk (the brain sends
  its own budget and the body clamps to its ceiling, so a disagreement tightens rather than
  breaks), but a repo-gate scan asserting the two literals match is the honest fix. It would live
  beside `linecap.py` and `dashcheck.py` and cost one small script.
- **A live-probe refresh.** The `/props` vision probe runs **once at startup**. A `llama-server`
  restarted without `--mmproj` mid-session leaves `capture_screen` advertised, so a capture would
  be taken, the user notified, and the turn tainted for an image the model cannot read: the full
  privacy cost for zero benefit. Re-probing per turn would make the inference adapter stateful,
  which is why it was not done; the cheap version is re-probing when a swap changes residency,
  since that is the only thing in the system that restarts a model server.
- **JPEG or WebP for a photographic screen.** Measurement puts JPEG q80 at roughly a quarter of
  PNG's bytes on incompressible content (0.97 MB vs 4.33 MB at 1600x900). It is a **body-side
  swap behind an unchanged seam**: `ImageBlob.mime_type` already carries the format, the brain's
  allow-list already lists both, and nothing in the brain decodes. Worth doing when bytes on the
  wire start mattering; PNG's losslessness is worth more while legibility is the open risk.
- **A content-addressed `AttachmentStore`, if accountability outweighs zero retention.** Today a
  reopened chat shows no evidence of what the assistant saw, and the audit line records
  dimensions, a byte count and a timestamp only, so a later dispute about what a capture
  contained cannot be answered from the store. That is a deliberate cost, not an oversight. The
  right shape if it ever needs paying is a content-addressed store with the message carrying a
  reference, plus a garbage-collection answer and a `delete` cascade.
- **An image arm of the injection-defence harness.** The two arms measured by hand (an
  instruction painted into the pixels, with and without a hardened preamble) both showed the same
  thing: not obeyed, transcribed verbatim. That is one corpus of one. A real arm against a
  rendered-payload corpus belongs in the existing harness, and its number gets published whatever
  it says.
- **The accepted residual the guardrail cannot catch.** Strict redaction removes a URL the model
  reproduces. It cannot catch one the model **retypes with a space**, defangs, or describes in
  words. The opaque bit closes the transcription path, not the paraphrase path, and no output
  filter can close the latter.
- **Per-source memory rules, so a vision turn can be remembered deliberately.** An opaque turn is
  dropped from durable memory outright, which is the safe default and a blunt one: "remember that
  my invoice number is 4021" after a capture is lost. A per-source policy (this source may be
  recorded, that one may not) is the general fix, and it belongs with the per-provenance rules
  already recorded under [untrusted-content.md](untrusted-content.md).
- **A `Windows.Graphics.Capture` backend.** GDI renders hardware-overlay and DRM-protected
  surfaces **black, silently**, with no `CaptureError` to distinguish that from a genuinely dark
  screen. WGC also brings a free yellow OS capture border, which is the best privacy affordance
  on offer and the one thing consciously given up. It costs async frame arrival against a
  deliberately synchronous port, WinRT interop, a D3D11 staging copy, and a Windows 11 22H2 floor
  to control the border. Behind the unchanged `ScreenCapture` trait either way.
- **Multi-monitor and DPI reporting.** v1 is the primary display only, in physical pixels.
  `CaptureScreenRequest` reserves field 2 for a display index, and nothing enumerates monitors
  yet, which is exactly why the field was left unassigned.
- **Linux and macOS `ScreenCapture` backends.** Both crates carry `unimplemented!()` stubs that
  satisfy the trait, like every other OS port.
- **A uniform per-call deadline on `BodyService`.** Capture is the first call to carry one
  (`CORTEX_BODY_CAPTURE_TIMEOUT_S`), because a blit plus an encode is the first that can park a
  host thread. `get_volume`, `set_volume`, and `notify` keep their live-validated no-deadline
  behaviour; changing what works is not a change this slice earned.
- **`RESOURCE_EXHAUSTED` classification.** A capture the ladder refuses maps to `Internal`, which
  is honest but coarse: the brain cannot tell "your screen is too complex to send" from "the
  backend broke". A distinct status (and a distinct message the cortex could relay) is a small
  mapping change on both sides.
- **Pixel-level screening in the body.** The body is the only side that knows what is on the
  screen before it crosses the seam, so it is the only side that could redact a region (a
  password field, a specific window) rather than refuse a whole capture. Nothing in the design
  precludes it: the policy already lives in pure core, where a screening pass would join it.
