# A call cut off by a down sidecar blames the file

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-13

When a sidecar stops during a call, the dispatcher hands the model the `ToolError` text `MCP sidecar
unavailable` as an `is_error` result. With `mcp-filesystem` killed during `read_text_file`, the
model replied that "the file `choir-rota.txt` appears to be unavailable or inaccessible as the
content returned is "MCP sidecar unavailable"": it blamed the file and quoted the error, and nothing
told the person that the file tool server had stopped
([readings](../../readings/store-and-sidecar-outages.md#the-filesystem-sidecar)). A listing that
finds the sidecar down already sends a status naming it (ADR-0009 decision 8); a call cut off
mid-flight does not.

## Reproduce

On the GPU stack with the file sidecar, ask the overlay to read a file, `docker pause` the
`mcp-filesystem` container once the brain audits a `list_directory` call, and `docker kill` it a few
seconds later.

## What to do

The rows, the candidate text and the pass rule are written in
[tool-call-cut-off.md](../../readings/tool-call-cut-off.md): run the 5 baseline rows, then, if the
defect reproduces, build the candidate (a typed error from the registry adapter that the skip
wrapper turns into the text written there) and run its 5 rows. Ship it only on a pass. A
`forgoing` status naming the server when such a call fails is decided apart from the rows.

## History

- 2026-10-13: filed when the down-sidecar listing was changed to answer the turn without the
  sidecar's tools; this half, the call already running, was left as it is.
- 2026-10-13: wrote the rows, the candidate's text and the pass rule into the readings before
  any row was drawn; the rows are not run yet.
