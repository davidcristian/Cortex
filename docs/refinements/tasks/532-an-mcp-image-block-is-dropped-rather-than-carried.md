# An MCP image block is dropped by the adapter rather than passed on as a result image

**Status:** done 2026-09-04
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`McpToolRegistry.invoke` (`brain/packages/tools/src/cortex_tools/registry.py`) joins the
`TextContent` blocks of a `CallToolResult` and builds the `ToolResult` without `images`, so an
`ImageContent` block a sidecar returns is discarded: it reaches neither the model nor the audit log,
and `ToolResult.images` is a field only a built-in (`CaptureScreenTool`) fills today. The own-text
overlay's rule that a result with an image is never re-stamped is therefore tested at the core over
the fake, and the tools contract asserts the adapter's own behaviour instead.

Nothing is wrong today, since no sidecar this repo composes returns an image. It matters the day one
does: the model would read the text and never learn a picture came with it, and the taint boundary
for pixels (`TaintLedger.opaque`, ADR-0029) would not fire for a picture the adapter threw away.
Closing it means decoding an `ImageContent` block into an `ImagePart` in the adapter, which needs the
block's dimensions, since `ImagePart` requires a width and a height and MCP's block has neither.

## History

- 2026-09-02: opened by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md), whose
  contract ran the own-text overlay over the real `McpToolRegistry` and found the image case
  unreachable there.
- 2026-09-04: closed. The premise held to the line: `invoke` built the `ToolResult` with no
  `images`, and `test_own_text_contract.py` had a test asserting the drop. `cortex_tools/blocks.py`
  now reads every `ImageContent` block into an `ImagePart`, taking the width and height from the PNG
  header rather than widening the part's contract or waiting on a sidecar declaration; `invoke`
  passes the result on and crosses an `ImageError` as `ToolError`. The image test now runs over both
  halves of the own-text contract, and the decision is ADR-0009 decision 19. PNG is the only format
  sized, which [R-549](549-jpeg-and-webp-image-blocks-are-refused-rather-than-sized.md) covers.
