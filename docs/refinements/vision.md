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
Linux and macOS backends, a uniform per-call deadline, `RESOURCE_EXHAUSTED` classification,
pixel screening in the body, carrying a picture (or at least the `opaque` bit) across a model
swap, an outcome-driven capture indicator, the two agent-Docker validations this slice left
unrun, and the host-side Windows validation of the whole capture path.

Two bookkeeping notes, both settled 2026-07-19, so the names above can be reconciled against the
bullets below without re-deriving them. Region and window capture and legibility at 4K share one
bullet (the risk and the fix that closes it), which is why the names outnumber the bullets by one.
And **the accepted residual the guardrail cannot catch** has a bullet but is deliberately not
counted; the reason is recorded on the bullet itself.

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
  **Excluded from this area's open count on purpose, stated 2026-07-19.** ADR-0029's own Deferred
  paragraph lists it beside the rest, and it was missing from the Open items line above without
  anything saying why, which is the silent kind of omission this file exists to catch. It is
  excluded because it names no work: an accepted limitation with no fix on offer (no output filter
  closes a paraphrase) would sit in a backlog that must be empty before the README ships and never
  leave it. It stays here as the record of what was accepted and on what reasoning, which is the
  role a declined entry plays, and it reopens only if someone proposes a mechanism that closes the
  paraphrase path, which would be a different kind of defence than an output filter.
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
- **Carrying a picture, or at least the `opaque` bit, across a model swap.** Named in ADR-0029's
  own Deferred paragraph and written down here on 2026-07-19, having been missed when the slice
  closed. Nothing persists an in-turn image: no session store, and no handoff record either, whose
  codec enumerates message fields by name so a `Message.images` would have been dropped in
  silence. The **user-visible** consequence is live: a turn that looked at the screen cannot hand
  over to the deep model at all, and the conductor ends it with a note telling the user to ask
  again in a fresh message. `HandoffRecord` does not carry the `opaque` bit either, so
  `taint_ledger()` rebuilds it at `False`; that is sound only because no opaque turn can reach a
  record (the conductor refuses first), and carrying the bit as defence in depth is the cheap half
  of this entry. The expensive half is pixels themselves, which wants the `AttachmentStore` above,
  and a capability argument still says no: no brain-tier candidate on the mount has a projector,
  so a replayed picture would be unreadable even if it survived.
- **An outcome-driven capture indicator.** The overlay's dot is lit by the `ToolActivity` chip,
  which the brain emits just *before* the dispatch, so it means "the assistant asked to look at
  your screen" and its label says exactly that. It cannot say the screen was read, because no
  outcome crosses the seam: the host kill switch, a self-exclusion that failed closed, an
  unreachable body, and a declined gated capture all produce the same event. A stronger surface
  (the one consent surface that would then match the body's own OS receipt) needs a post-dispatch
  signal on the `Converse` stream, which is a proto field plus a reducer arm plus a tool-loop
  emission point, so it is a seam change rather than an increment.
- **Two agent-Docker validations this slice listed as still to run.** Written down 2026-07-19,
  having lived only in [ADR-0029](../adr/ADR-0029-vision-screen-capture.md)'s Consequences with
  nothing tracking them, which is how work owed becomes work forgotten. That ADR named four
  measurements as still to run when it was accepted. Two of them ran and are recorded in its
  2026-07-18 agent-validation section (the whole path through the real `LlamaCppBackend` rather
  than raw HTTP, and an injection arm on the shipped payload). Two did not: **whether thinking
  needs disabling on a vision turn** under the shipped parts payload, and **`llama-server`'s
  `mmproj`-less error body text**, which that ADR also carries on its assumptions list precisely
  because the bounded 300-character non-2xx excerpt was built to surface it, so the excerpt's whole
  value rests on a string nobody has read. Both are **agent-side, not host-side**, which is why
  they belong in this backlog rather than on a user list: the same 8 GB dev GPU that ran the
  2026-07-18 validation holds the cortex beside its projector, so nothing about them needs the
  host hardware. The disable-thinking lever itself is a separate open entry
  ([inference-model-manager.md](inference-model-manager.md)); what is unmeasured here is only
  whether a vision turn is the case that needs it.
- **Host-side Windows validation of the whole capture path.** The one part of this slice no gate
  can reach, and the only one on the ADR's host-only list without a backlog line until
  2026-07-19. In order: the real GDI blit of a live desktop; **capturing while the overlay is
  visible, to prove `WDA_EXCLUDEFROMCAPTURE` held**, which is the check nothing else can stand in
  for (if it silently fails, the self-injection loop is live); per-monitor DPI behaviour; the
  body-authored receipt appearing and reading well; GDI's black-rectangle behaviour on
  hardware-overlay and DRM-protected surfaces; and hotkey-to-answer latency with its vision
  surcharge. Runbook: [../runbooks/vision.md](../runbooks/vision.md).
- **Pixel-level screening in the body.** The body is the only side that knows what is on the
  screen before it crosses the seam, so it is the only side that could redact a region (a
  password field, a specific window) rather than refuse a whole capture. Nothing in the design
  precludes it: the policy already lives in pure core, where a screening pass would join it.
