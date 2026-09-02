# An MCP image block is dropped by the adapter rather than carried as a result image

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** a sidecar this repo composes answers a call with an `ImageContent` block, or a
contract check needs the real adapter to hand the overlay a result that carries an image.

Opened 2026-09-02 by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md), whose
contract ran the own-text overlay over the real `McpToolRegistry` and found the image case
unreachable there. `McpToolRegistry.invoke` (`brain/packages/tools/src/cortex_tools/registry.py`)
joins the `TextContent` blocks of a `CallToolResult` and builds the `ToolResult` without
`images`, so an `ImageContent` block a sidecar returns is discarded: it reaches neither the model
nor the audit log, and `ToolResult.images` is a field only a built-in (`CaptureScreenTool`)
fills today. The overlay's rule that a result carrying an image is never re-stamped is therefore
exercised at the core over the fake, and the tools contract asserts the adapter's own behaviour
instead: the exact text beside an image block arrives as the exact text and is re-stamped, which
is sound because the dropped block reaches nothing.

Nothing is wrong today. No sidecar this repo composes returns an image, and dropping a block the
model never sees loses nothing the turn had. It bites the day one does: the model would read the
text and never learn a picture came with it, and the taint boundary for pixels (`TaintLedger.opaque`,
ADR-0029) would not fire for a picture the adapter threw away.

**What would close it.** Decode an `ImageContent` block into an `ImagePart` in the adapter, which
needs the block's dimensions (`ImagePart` requires a width and a height and MCP's block carries
neither, so the adapter would have to open the bytes or the part's contract would have to admit
unknown dimensions), carry it on `ToolResult.images`, and add the arm to `test_own_text_contract.py`
in which the exact text beside an image stays untrusted through the real adapter. An oversized or
unlisted image should raise `ImageError` into a `ToolError`, the fail-closed shape every other
adapter failure takes.

## Trail

- 2026-09-02: opened by the close of [530](530-a-sidecars-own-text-is-re-stamped-trusted.md).
