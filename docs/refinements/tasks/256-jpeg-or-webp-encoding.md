# JPEG or WebP for a photographic screen

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** Bytes on the wire starting to matter.

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

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-08-06: re-read against the capture edge that moved that morning and correctly stayed put, the
  2048 px default having moved its numbers without moving its trigger. The sibling
  `RESOURCE_EXHAUSTED` entry had not re-read itself against the same change, which is what made that
  evening's pass over it owed.
- 2026-08-09: covered by the trigger sweep that ran against the tree over the whole fix-when-it-bites
  bucket and fired nothing. The index recorded that sweep so the next reader would spend the pass
  elsewhere instead of re-deriving the same verdicts, and it read every entry in the bucket against
  the code rather than against the entry's own text.
