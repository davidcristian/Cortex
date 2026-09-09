# JPEG or WebP for a photographic screen

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09
**Trigger:** A screen someone owns firing the capture policy's halving ladder at the
shipped 2048 px edge, which is either of the two ladder assertions in `capture_bytes.rs` failing:
the four realistic frames on a 4K display, or the same grainy photograph on the three display sizes
the second one draws it at, no longer fitting inside `CORTEX_BODY_MAX_IMAGE_BYTES`.

Measurement puts JPEG q80 at roughly a quarter of
PNG's bytes on incompressible content (0.97 MB vs 4.33 MB at 1600x900). It is a **body-side
swap behind an unchanged seam**: `ImageBlob.mime_type` already carries the format, the brain's
allow-list already lists both, and nothing in the brain decodes. Worth doing when bytes on the
wire start mattering; PNG's losslessness is worth more while legibility is the open risk. The
2048 px default edge moved the numbers without moving the trigger, and the margin behind it is
narrower than a 4K measurement alone reports. On a 4K display a photographic screen costs 3.59 MB
at 2048 px against 2.05 MB at 1600 px, and 4.67 MB with heavy grain. The costliest display is the
middle one rather than the biggest, because how much grain survives is set by the ratio between the
display and the requested edge: the same heavy-grain photograph is 5016491 B on a 2560x1440 desktop,
79% of the ceiling, against 74% at 4K and 71% at 1920x1080. So the worst screen a person owns sits a
fifth below the ceiling rather than a quarter (measured 2026-08-06,
[`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs)).

## Trail

- 2026-09-09: claims re-derived from the code. Still not fired, and every structural claim holds:
  `ImageBlob.mime_type` carries the format
  ([proto/body.proto](../../../proto/body.proto)), `ALLOWED_MIME_TYPES` in
  [images.py](../../../brain/packages/core/src/cortex_core/images.py) lists PNG, JPEG and WebP, and
  that module's own docstring says the core never decodes an image. What was stale is the margin.
  Both this entry and the restatement below read the 4K table only, where the ADR narrowed that
  table on the day it was measured: `capture_bytes.rs` has a second ladder assertion,
  `a_display_nearer_the_requested_edge_is_the_expensive_one`, and the costliest display in it is
  2560x1440 at 79% of the ceiling rather than the 4K frame at 74%. The trigger above now names both
  assertions, and the body carries the display numbers.
- 2026-09-06: **Not fired**, and the trigger above is restated, because "bytes starting to
  matter" is a judgement rather than a count. The number that decides it is already in the tree:
  the capture policy halves the requested edge when the encoded frame is over
  `CORTEX_BODY_MAX_IMAGE_BYTES`, 6291456 bytes as the body compose override ships it, and
  `a_screen_worth_reading_text_off_stays_inside_the_ceiling_at_the_edge_the_brain_asks_for` asserts
  that none of the text desktop, the wallpaper desktop, the photograph and the heavily grained
  photograph fires that ladder at 2048 px, the worst of them costing 4.67 MB against the ceiling.
  So the swap is owed when one of those frames crosses the ceiling or a live capture comes back
  halved, and not before.
- 2026-09-06: The vision sittings run over this night do not bear on the trigger, though their
  vocabulary looks as if it does. Their payload sweep varies the rendered size of an injection
  payload in pixels, and their two budgets are values of `CORTEX_IMAGE_MAX_TOKENS` at the model
  host. Neither is bytes on the seam, and no sitting encoded a frame.
- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-08-06: re-read against the capture edge that moved that morning and correctly stayed put, the
  2048 px default having moved its numbers without moving its trigger. The sibling
  `RESOURCE_EXHAUSTED` entry had not re-read itself against the same change, which is what made that
  evening's pass over it owed.
- 2026-08-09: covered by the trigger sweep that ran against the tree over the whole fix-when-it-bites
  bucket and fired nothing. The index recorded that sweep so the next reader would spend the pass
  elsewhere instead of re-deriving the same verdicts, and it read every entry in the bucket against
  the code rather than against the entry's own text.
