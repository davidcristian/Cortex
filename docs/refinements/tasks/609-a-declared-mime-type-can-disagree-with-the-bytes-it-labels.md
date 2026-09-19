# A declared mime type can disagree with the bytes it labels

**Status:** open, fix when it bites
**Area:** tools-mcp
**Trigger:** an inference engine this repo runs refuses or misreads a picture whose `data:` label
names another format than its bytes; llama.cpp build 10680 reads all four such pairs tried by
their bytes.
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-19

Opened 2026-09-08 by the close of
[549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md), which made
`cortex_tools/headers.py` size a JPEG and a WebP as well as a PNG.

`blocks.py` builds an `ImagePart` from the mime type the MCP block declares and the size the bytes
state, and the two are read independently: `image_size` picks its reader from the signature the
bytes carry, and the declaration is judged only by the core's `ALLOWED_MIME_TYPES`, which has
listed all three formats since it was written. So a block is accepted whenever some reader claims
its bytes, whatever it declares them to be, and all six mismatched pairs of the three formats are
accepted today. A block declaring `image/png` while carrying a JPEG is sized correctly and reaches
the model as a `data:image/png` URI wrapping JPEG bytes.

The sized formats widened that rather than opening it, which this entry had backwards until the
two were measured. The ADR-0009 image-carry addendum gave as its reason for leaving the
declaration unchecked that a disagreeing one fails on the size read anyway, since only a PNG had a
size to read. That held for a mislabeled JPEG or WebP and never for a mislabeled PNG: the size
read looked at the bytes alone, so PNG bytes declared `image/jpeg` or `image/webp` were sized and
accepted before the second and third readers landed, exactly as they are after. What those readers
changed is how many mismatches are reachable, from the two a PNG payload can carry to all six.

**Why it was left.** Checking the declaration against the signature is three lines, and the
decision behind them is not. The image-carry addendum states that the mime type is the sidecar's
declaration, judged against the core's allow-list rather than against the bytes, and that this is
the same standing the body's declared type has. Making the tools adapter sniff and compare would
make it stricter than the seam the body's captures cross, which is a change to what a declaration
means across both paths rather than a fix to one reader. The bite is also bounded: no decoder in
this process opens the bytes, so a mislabeled block is a wrong label rather than a wrong parse. The
shipped engine reads the payload by its bytes: llama.cpp build 10680 answered correctly about a
JPEG labeled `image/png`, a PNG labeled `image/jpeg` and a JPEG labeled `image/webp`, and logged
nothing about the label (the 2026-09-19 trail bullet has the run). And the one shipped sidecar
that returns pictures takes the type from a file's name: the pinned filesystem server's
`read_media_file` reads the extension alone, so a JPEG saved as `photo.png` under
`CORTEX_TOOLS_ROOT` crosses the seam declared `image/png`.

**What would close it.** Either decide that a declared type naming one of the three read formats
must match the signature, refuse the mismatch in `blocks.py`, and say at ADR-0009 what that means
for the body's declared type, which the same rule would have to reach eventually (on the shipped
engine that refuses a misnamed file the model would have read correctly); or record that
the declaration stays unchecked, and say in `docs/modules/brain-tools.md` that the filesystem
sidecar labels by extension and that the shipped engine reads such a picture correctly and says
nothing, so an operator sees no symptom at all. The second close no longer needs an engine that
refuses before it can be written, since the engine this repo runs was asked.

## Trail

- 2026-09-08: opened by the close of
  [549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md), whose
  [ADR-0009 sized-formats addendum](../../adr/ADR-0009-tools-mcp.md) records which sentence of the
  image-carry addendum stopped being true when the second and third readers landed.
- 2026-09-09: claims held against the code, and the word "now" removed from the title and the body
  because it dated the mismatch to the sized-formats landing. The pre-landing reader was run over
  the tools suite's own pictures: PNG bytes declared `image/jpeg` and PNG bytes declared
  `image/webp` were both accepted, and only the JPEG declared `image/png` was refused. So a
  mislabeled picture reached the model before three formats were sized, and the sentence the
  sized-formats addendum corrected was already false for a PNG payload on the day it was written.
  Everything else holds: `blocks.py` still reads the declaration and the size independently, and
  `ALLOWED_MIME_TYPES` has carried all three types since the capture path was written. Recorded in
  the ADR-0009 addendum of this date.
- 2026-09-13: re-derived and left open. The trigger has not fired: nothing in the tree records a
  picture that reached the model under a type its bytes are not, and no inference backend here has
  refused one. The mechanism is unchanged. `_image_part` in
  `brain/packages/tools/src/cortex_tools/blocks.py` still builds the part from `block.mimeType`
  and from `image_size(data)`, which picks its reader off the signature the bytes carry, and the
  function's own docstring still states that the declaration is checked against the core's
  allow-list rather than against the bytes. `ALLOWED_MIME_TYPES` in `cortex_core/images.py` still
  lists all three formats, so all six mismatched pairs are still accepted.
- 2026-09-19: re-derived, the trigger rewritten and the bite measured. The code claims hold:
  `_image_part` in `blocks.py` still builds the part from `block.mimeType` and `image_size(data)`,
  and `ALLOWED_MIME_TYPES` still lists the three formats. The old trigger's first clause, a picture
  reaching the model under a type its bytes are not, is ordinary behavior of the shipped filesystem
  sidecar (its `read_media_file` maps `.png`, `.jpg`, `.jpeg` and `.webp` to a type by extension,
  read in the `@modelcontextprotocol/server-filesystem@2026.1.14` package the compose file pins), so
  it named an event with no cost. The second clause asked whether an engine refuses a mismatch,
  which was measured instead of waited for. A CPU-only `ghcr.io/ggml-org/llama.cpp:server` (build
  10680, commit d7bd3bfca, the same build as the cached `server-cuda` image the model host is built
  on) served gemma-4-E2B with its projector, the card being held by a GPU sitting. Six 256 by 256
  single-color pictures made with ffmpeg went in a user message as `data:` URIs, asking for the
  color: PNG and JPEG under their own labels, then a red JPEG labeled `image/png`, a red PNG labeled
  `image/jpeg`, a blue JPEG labeled `image/webp` and a blue JPEG labeled `image/png`. All six
  returned 200 with the right color, and the server log carried no line about a label. The strings
  the server library carries for a `data:` URI are `data:image/`, `uri must be base64 encoded` and
  `Invalid base64 value`, which fits a parse that checks the prefix and the encoding and leaves the
  format to the decoder. The trigger now names the case that would cost something, an engine that
  refuses or misreads, and records that the build shipped today does neither. Recorded in the
  ADR-0009 shipped-pair addendum.
