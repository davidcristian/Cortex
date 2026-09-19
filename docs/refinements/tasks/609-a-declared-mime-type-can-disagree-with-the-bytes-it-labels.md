# A declared mime type can disagree with the bytes it labels

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Trigger:** an inference engine this repo runs refuses or misreads a picture whose `data:` label
names another format than its bytes; llama.cpp build 10680 reads all four such pairs tried by
their bytes.
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19

`blocks.py` builds an `ImagePart` from two values it reads independently: the mime type the MCP
block declares, which is checked only against the core's `ALLOWED_MIME_TYPES`, and the size, which
`image_size` reads from the signature in the bytes. `ALLOWED_MIME_TYPES` has listed PNG, JPEG and
WebP since it was written, so all six mismatched pairs of those three formats are accepted. A block
declaring `image/png` while containing JPEG bytes is sized correctly and reaches the model as a
`data:image/png` URI wrapping JPEG bytes.

Nothing in this process decodes the bytes, so a mismatch is a wrong label rather than a wrong parse,
and the engine this repo runs ignores the label. The one sidecar that returns pictures labels by
file name: the filesystem server's `read_media_file` maps the extension, so a JPEG saved as
`photo.png` under `CORTEX_TOOLS_ROOT` is declared `image/png`.

**Why it was left.** Comparing the declaration with the signature is three lines, but it would make
the tools adapter stricter than the interface the body's captures cross, where the declared type is
trusted the same way ([ADR-0009](../../adr/ADR-0009-tools-mcp.md) decision 19).

**What would close it.** Either refuse the mismatch in `blocks.py` and say in ADR-0009 what that
means for the body's declared type, or record that the declaration stays unchecked and note in
`docs/modules/brain-tools.md` that the filesystem sidecar labels by extension and that the shipped
engine reads such a picture correctly, so an operator sees no symptom at all.

## History

- 2026-09-08: opened by the close of
  [549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md), which made
  `cortex_tools/headers.py` size a JPEG and a WebP as well as a PNG.
- 2026-09-09: the word "now" was removed from the title and the body, because it dated the mismatch
  wrongly. The earlier reader accepted PNG bytes declared `image/jpeg` and PNG bytes declared
  `image/webp`, and refused only a JPEG declared `image/png`, so mislabeled pictures reached the
  model before three formats were sized. Sizing three formats widened the problem from two
  reachable mismatches to six.
- 2026-09-13: checked again and left open. `_image_part` in
  `brain/packages/tools/src/cortex_tools/blocks.py` still builds the part from `block.mimeType` and
  from `image_size(data)`, and `ALLOWED_MIME_TYPES` in `cortex_core/images.py` still lists all three
  formats.
- 2026-09-19: checked again, and the trigger was rewritten after the cost was measured. Its old
  first clause, a picture reaching the model under a type its bytes are not, is ordinary behavior of
  the filesystem sidecar (`@modelcontextprotocol/server-filesystem@2026.1.14` maps `.png`, `.jpg`,
  `.jpeg` and `.webp` to a type by extension), so it named an event that costs nothing. The second
  clause was measured instead of waited for. A CPU-only `ghcr.io/ggml-org/llama.cpp:server` (build
  10680, commit d7bd3bfca, the same build as the cached `server-cuda` image the model host is built
  on) served gemma-4-E2B with its projector. Six 256 by 256 single-color pictures made with ffmpeg
  went into a user message as `data:` URIs asking for the color: a PNG and a JPEG under their own
  labels, then a red JPEG labeled `image/png`, a red PNG labeled `image/jpeg`, a blue JPEG labeled
  `image/webp` and a blue JPEG labeled `image/png`. All six returned 200 with the right color, and
  the server log said nothing about a label. The reading is in
  [tool sidecar calls](../../readings/tool-sidecar-calls.md).
