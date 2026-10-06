# A declared mime type can disagree with the bytes it labels

**Status:** open, waiting for its trigger
**Area:** tools-mcp
**Trigger:** an inference engine this repo runs refuses or misreads a picture whose `data:` label
names another format than its bytes; llama.cpp build 10680 reads all four such pairs tried by
their bytes.
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-06

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

**Why it was left.** It would make the tools adapter stricter than the interface the body's
captures cross, where `GrpcBodyGateway` builds the `ImagePart` from the declared type the same way
([ADR-0009](../../adr/ADR-0009-tools-mcp.md) decision 19). Since 2026-09-25 one image source is
checked: a picture the user attaches must start with the signature of its declared type
(`signature_matches` in `cortex_core/attachments.py`,
[ADR-0070](../../adr/ADR-0070-user-attached-images.md) decision 4), and that function takes an
`ImagePart`, so the same check in `blocks.py` is one call. The two sources differ in what a
mismatch means. The body encodes an attachment's bytes itself, so a mismatch there is a body
defect. A tool's label comes from a file name the user chose, and the engine reads such a picture
correctly, so refusing it would turn a picture the model can read into a `ToolError`.

**What would close it.** If the trigger fires, the fix is to label the part from its bytes rather
than to refuse it: `image_size` already picks its reader by the signature, so it can also return
the type that signature names, and the part reaches the engine under the right label. ADR-0009
decision 19 would then say the label is the bytes' and not the sidecar's. Until then the record of
leaving it is mostly written: decision 19 says the declaration is checked against the allow-list
and not against the bytes, its Consequences say a mislabeled image reaches the model under the
sidecar's label, and the Image blocks section of `docs/modules/brain-tools.md` says the same. None
of them says that the filesystem sidecar labels by extension and that the shipped engine reads
such a picture by its bytes. That note would close this entry, and would also drop the only record
that a newer engine build needs the four pairs tried again.

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
- 2026-10-02: checked again and left open, with the reason and the remedy corrected. The trigger
  has not fired: both cached engine images (`server` `db057ec90de0` and `server-cuda`
  `952424b09abc`) date from 2026-08-29 and are read as `b10680` in the readings since, and the one
  commit since 2026-09-19 on `blocks.py`, `headers.py` and `images.py` only reworded error text.
  The reason for leaving it named captures as the only body interface and called the check three
  lines; since 2026-09-25 attachments refuse a mismatch through `signature_matches`, which makes
  the check one call, and the body now says why the tools path still should not refuse. The remedy
  offered a refusal, which would break reading a JPEG saved as `photo.png`; it now relabels from
  the bytes. The record of the unchecked declaration that the entry offered as a close was already
  in the ADR and the module doc before the last check; only the operator note is missing.
