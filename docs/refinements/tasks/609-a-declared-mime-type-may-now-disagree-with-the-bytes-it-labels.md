# A declared mime type may now disagree with the bytes it labels

**Status:** open, fix when it bites
**Area:** tools-mcp
**Trigger:** a picture reaches the model under a mime type its bytes are not, either because a
sidecar declared the wrong one or because an inference backend refuses a `data:` URI whose label
and payload disagree.
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-09-08 by the close of
[549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md), which made
`cortex_tools/headers.py` size a JPEG and a WebP as well as a PNG.

`blocks.py` builds an `ImagePart` from the mime type the MCP block declares and the size the bytes
state, and the two are read independently: `image_size` picks its reader from the signature the
bytes carry, and the declaration is judged only by the core's `ALLOWED_MIME_TYPES`. While PNG was
the only format sized, a declaration disagreeing with the bytes failed on the size read, which the
ADR-0009 image-carry addendum recorded as the reason the declaration needed no check of its own.
That is no longer so. A block declaring `image/png` while carrying a JPEG is now sized correctly
and reaches the model as a `data:image/png` URI wrapping JPEG bytes.

**Why it was left.** Checking the declaration against the signature is three lines, and the
decision behind them is not. The image-carry addendum states that the mime type is the sidecar's
declaration, judged against the core's allow-list rather than against the bytes, and that this is
the same standing the body's declared type has. Making the tools adapter sniff and compare would
make it stricter than the seam the body's captures cross, which is a change to what a declaration
means across both paths rather than a fix to one reader. The bite is also bounded: no decoder in
this process opens the bytes, so a mislabeled block is a wrong label rather than a wrong parse, and
the label reaches an inference backend that either sniffs the payload or refuses it.

**What would close it.** Either decide that a declared type naming one of the three read formats
must match the signature, refuse the mismatch in `blocks.py`, and say at ADR-0009 what that means
for the body's declared type, which the same rule would have to reach eventually; or record that
the declaration stays unchecked and that a mislabeled picture is the sidecar's defect, and say in
`docs/modules/brain-tools.md` what an operator sees when an inference backend rejects one.

## Trail

- 2026-09-08: opened by the close of
  [549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md), whose
  [ADR-0009 sized-formats addendum](../../adr/ADR-0009-tools-mcp.md) records which sentence of the
  image-carry addendum stopped being true when the second and third readers landed.
