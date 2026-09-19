# JPEG and WebP image blocks are refused rather than sized

**Status:** done 2026-09-08
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`cortex_tools/blocks.py` compares the PNG signature and reads the width and height from bytes 16 to
24, the two integers PNG requires the IHDR chunk to state first. That is a read at a fixed offset.
JPEG states its size in an SOF segment a reader has to walk the segment chain to find, and WebP in
one of three container forms (`VP8 `, `VP8L`, `VP8X`), each with its own layout. Both are in the
core's `ALLOWED_MIME_TYPES`, so both are formats an `ImagePart` may legally hold, and both were
refused here.

The refusal is reachable from the composed stack: the filesystem sidecar's allow list in
`docker/docker-compose.tools.yml` has named `read_media_file` since 2026-07-03, and that tool exists
to return a media block, so an operator who puts a JPEG under `CORTEX_TOOLS_ROOT` reaches it without
writing anything. Walking a segment chain over attacker-controlled bytes is a larger step than a
read at a fixed offset, since it follows lengths the bytes themselves state, which
`cortex_core/images.py` says the brain does not do.

## History

- 2026-09-04: opened by the close of
  [532](532-an-mcp-image-block-is-dropped-rather-than-carried.md), whose ADR-0009 decision 19
  records why the size is read from the PNG header and what a JPEG or WebP would cost.
- 2026-09-07: checked again and the entry's own reasons repaired. No call in this repo had returned
  a JPEG or WebP block, but both reasons recorded for leaving it were false the day they were
  written: `CORTEX_TOOLS_ALLOW__FILESYSTEM` has named `read_media_file` since 2026-07-03, so the
  refusal is reachable from the shipped compose, and the sidecar that reaches it is the third-party
  reference filesystem server at a fixed version rather than one this repo writes. Moved to
  actionable and deliberately not done that day, since the readers owe byte-level tests and a
  mutation table.
- 2026-09-08: done, as a bounded JPEG segment walk and a WebP container read. The three readers are
  a module of their own, `brain/packages/tools/src/cortex_tools/headers.py`, and `blocks.py` keeps
  the path from a block to an `ImagePart`. The walk stops at 512 segments, refuses a length below
  the two bytes the length field occupies so the cursor always advances, and compares every offset
  against the buffer before reading it, so a truncated or self-referential chain raises `ImageError`
  rather than looping or raising `struct.error`. All three WebP container forms are read from the
  first chunk. The fixture module has one real picture per form, written by ffmpeg, and
  `test_headers.py` builds every malformed container by hand. Twelve mutations were measured over
  the 108-test `brain/packages/tools` suite; one survived and was answered with a new test. The
  decision is ADR-0009 decision 19. Opens
  [609](609-a-declared-mime-type-can-disagree-with-the-bytes-it-labels.md): with three formats
  sized, a declaration naming the wrong one is no longer caught by the size read.
