# JPEG or WebP for a photographic screen

**Status:** open, waiting for its trigger
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-24
**Trigger:** either ladder assertion in `body/crates/core/tests/capture_bytes.rs` failing: the four
realistic frames on a 4K display, or the same grainy photograph on the three display sizes the
second one draws it at, no longer fitting inside `MAX_CAPTURE_BYTES` (6291456, in
`body/crates/core/src/os/screen_policy.rs`, the body's copy of the `CORTEX_BODY_MAX_IMAGE_BYTES`
default) at the test's `BRAIN_EDGE` (2048, which crosscheck compares against the
`CORTEX_BODY_CAPTURE_MAX_EDGE` default). Both assertions are ignored tests that `just check` never
runs, so the reading is the hand run
`cargo test -p body-core --test capture_bytes --release -- --ignored --nocapture` from `body/`.
The frames are synthetic and seeded, so only those two numbers, the downscaler (`downscale` in
`body/crates/core/src/os/screen_image.rs`), or the `png` encoder crate (its version in
`body/Cargo.lock`) can move the result. A deployment that lowers either setting in its own
environment is not measured by the test.

JPEG q80 is roughly a quarter of PNG's bytes on incompressible content (0.97 MB against 4.33 MB at
1600x900). It is a body-side change behind an unchanged interface: `ImageBlob.mime_type` already
states the format, the brain's allow-list already lists both, and nothing in the brain decodes.
Worth doing when bytes on the wire start to cost something; PNG being lossless is worth more while
legibility is the open risk.

The margin is narrower than a 4K measurement alone shows. On a 4K display a photographic screen
costs 3.59 MB at 2048 px against 2.05 MB at 1600 px, and 4.67 MB with heavy grain. The costliest
display is the middle one rather than the biggest, because how much grain survives is set by the
ratio between the display and the requested edge: the same heavy-grain photograph is 5016491 B on a
2560x1440 desktop, 79% of the ceiling, against 74% at 4K and 71% at 1920x1080 (measured 2026-08-06,
[`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs)).

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-08-06: Re-read against the capture edge that moved that morning and correctly left open, the
  2048 px default having moved its numbers without moving its trigger.
- 2026-08-09: Covered by a review of the entries deferred until they cause a problem, which read
  every one against the code and found none had.
- 2026-09-06: Not triggered, and the trigger restated, because "bytes starting to matter" is a
  judgement rather than a count. The capture policy halves the requested edge when the encoded
  frame is over `CORTEX_BODY_MAX_IMAGE_BYTES`, 6291456 bytes as the body compose override ships it,
  and `a_screen_worth_reading_text_off_stays_inside_the_ceiling_at_the_edge_the_brain_asks_for`
  asserts that none of the four frames reaches that ladder at 2048 px.
- 2026-09-06: The vision measurement runs that night do not bear on the trigger, although their
  vocabulary looks as if they do. They vary the rendered size of an injection payload in pixels and
  the value of `CORTEX_IMAGE_MAX_TOKENS` at the model host. Neither is bytes on the wire, and no
  run encoded a frame.
- 2026-09-09: Claims checked against the code. Still not triggered, and every structural claim
  holds: `ImageBlob.mime_type` states the format
  ([proto/body.proto](../../../proto/body.proto)), `ALLOWED_MIME_TYPES` in
  [images.py](../../../brain/packages/core/src/cortex_core/images.py) lists PNG, JPEG and WebP, and
  the core never decodes an image. What was stale is the margin: both this entry and its
  restatement read the 4K table only, while `capture_bytes.rs` has a second ladder assertion,
  `a_display_nearer_the_requested_edge_is_the_expensive_one`, whose costliest display is 2560x1440
  at 79% of the ceiling.
- 2026-09-17: Re-run, not triggered. The hand run above passed all four tests and printed the same
  bytes as the 2026-08-06 measurement: 5016491 B (79%) for the grainy photograph on 2560x1440,
  4669961 B (74%) on 4K, 4500808 B (71%) on 1920x1080. No commit since 2026-09-09 touched
  `capture_bytes.rs` or `screen_policy.rs`. The trigger now says both assertions are ignored tests,
  so a green `just check` says nothing about it.
- 2026-09-24: Re-run, not triggered. The hand run passed all four tests and printed the same bytes
  as on 2026-09-17: 5016491 B (79%) on 2560x1440, 4669961 B (74%) on 4K and 4500808 B (71%) on
  1920x1080. Since then `screen_policy.rs` gained the capture's `target_width` and `target_height`,
  which describe the captured region and change no encoded byte, and `capture_bytes.rs` renamed one
  local. `screen_image.rs` and `body/Cargo.lock` have no commit since 2026-09-17, and the trigger
  now names both, so the downscaler and the encoder version are each one reading.
