# JPEG and WebP image blocks are refused rather than sized

**Status:** open, actionable
**Area:** tools-mcp
**Trigger:** a sidecar this repo composes answers a call with an `ImageContent` block whose mime
type is `image/jpeg` or `image/webp`, which fails the call today with an `ImageError` naming the
format.
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-04 by the close of
[532](532-an-mcp-image-block-is-dropped-rather-than-carried.md), which read an MCP image block's
size out of the PNG header because the block itself states no dimensions.

`cortex_tools/blocks.py` compares the PNG signature and reads the width and height from bytes 16
to 24, the two integers PNG requires the IHDR chunk to state first. That is a fixed-offset read.
JPEG states its size in an SOF segment a reader has to walk the segment chain to find, and WebP in
one of three container shapes (`VP8 `, `VP8L`, `VP8X`), each with its own layout. Both are in the
core's `ALLOWED_MIME_TYPES`, so both are formats an `ImagePart` may legally carry, and both are
refused here.

**Why it was left.** The reason first recorded here was that every sidecar this repo composes
returns text, so no format was reachable. That was already wrong when it was written: the
filesystem sidecar's shipped allow list in `docker/docker-compose.tools.yml` has named
`read_media_file` since 2026-07-03, and that tool exists to return a media block. So an operator
who puts a JPEG under `CORTEX_TOOLS_ROOT` reaches this refusal from the composed stack without
writing anything. What is true is the narrower thing: no call in this repo has returned such a
block yet, and PNG is what the capture path emits. A segment walk over attacker-controlled bytes is a
larger step than a fixed-offset read: it follows lengths the bytes themselves state, which is the
thing `cortex_core/images.py` says the brain does not do, so admitting one is a posture decision
rather than a few more lines. Refusing the two formats is louder than the silent drop that came
before it, and the failure names the format.

**What would close it.** Either a bounded JPEG SOF walk and a WebP container read in
`blocks.py`, each with the byte-level tests `test_blocks.py` already has a shape for and an
explicit bound on how far the walk may run, or a decision recorded at ADR-0009 that the adapter
reads PNG alone and a sidecar returning another format is a sidecar to fix. The second was written
here as the cheaper and honest default while every sidecar here is one this repo writes, and that
premise is false too: the filesystem server is a pinned third-party package, so "fix the sidecar"
means dropping `read_media_file` from the allow list rather than editing a server. Either close is
still available, but the second now costs a narrowed allow list and a runbook line saying why.

## Trail

- 2026-09-04: opened by the close of
  [532](532-an-mcp-image-block-is-dropped-rather-than-carried.md), whose ADR-0009 image-carry
  addendum records why the size is read from the PNG header and what a JPEG or WebP would cost.
- 2026-09-07: trigger re-derived and the entry's own reasons repaired. The trigger has not fired,
  since no call in this repo has returned a JPEG or WebP block, but the two reasons recorded for
  leaving it were both false the day they were written. `CORTEX_TOOLS_ALLOW__FILESYSTEM` has named
  `read_media_file` since 2026-07-03, so the refusal is reachable from the shipped compose rather
  than unreachable, and the sidecar that would reach it is the pinned reference filesystem server
  rather than one this repo writes. Moved to actionable on that, and deliberately not landed: a
  bounded JPEG segment walk and a WebP container read owe byte-level tests and a mutation table
  that this slot had no room for, and narrowing the allow list instead is a posture decision worth
  its own pass. Recorded in the ADR-0009 addendum of this date.
