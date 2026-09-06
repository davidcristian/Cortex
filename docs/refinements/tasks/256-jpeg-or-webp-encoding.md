# JPEG or WebP for a photographic screen

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** A screen someone owns firing the capture policy's halving ladder at the
shipped 2048 px edge, which is the four realistic frames of `capture_bytes.rs` no longer
fitting inside `CORTEX_BODY_MAX_IMAGE_BYTES`.

Measurement puts JPEG q80 at roughly a quarter of
PNG's bytes on incompressible content (0.97 MB vs 4.33 MB at 1600x900). It is a **body-side
swap behind an unchanged seam**: `ImageBlob.mime_type` already carries the format, the brain's
allow-list already lists both, and nothing in the brain decodes. Worth doing when bytes on the
wire start mattering; PNG's losslessness is worth more while legibility is the open risk. The
2048 px default edge moved the numbers without moving the trigger: a photographic screen costs
3.59 MB there against 2.05 MB at 1600 px, and 4.67 MB with heavy grain, which is still inside
the ceiling with room to spare (measured 2026-08-06,
[`capture_bytes.rs`](../../../body/crates/core/tests/capture_bytes.rs)).

## Trail

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
