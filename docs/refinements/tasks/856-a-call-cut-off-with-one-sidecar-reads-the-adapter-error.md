# A call cut off with one sidecar reads the adapter's error

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-14

With only one tool server configured, `build_tool_registry` uses no `AggregateToolRegistry`, so
`SkipUnavailableToolRegistry.invoke` passes a call straight to the adapter. A call cut off when the
server stops reads `MCP sidecar unavailable` from `ReconnectingMcpToolRegistry`, or the
`BoundedToolRegistry` deadline's text, never the `SERVER_DOWN_MSG` text the aggregate returns for
the same stop with two or more servers. The text is accurate, but under `fail` the model blamed
the file and quoted it ([readings](../../readings/store-and-sidecar-outages.md#the-filesystem-sidecar)),
and no row has been drawn for it under `skip`.

## Reproduce

On the GPU stack with only the file sidecar, ask to read a file, `docker pause` the
`mcp-filesystem` container once the brain audits a `list_directory` or `search_files` call, and
`docker kill` it 8 s later.

## What to do

Run the rows written in [tool-call-cut-off.md](../../readings/tool-call-cut-off.md#one-sidecar).
If the defect reproduces, design a candidate that names the server for a call cut off on this path
and run its rows. A call that failed after the request was sent may have run, so its text cannot
say the call did not run, as `SERVER_DOWN_MSG` does.

## History

- 2026-10-14: filed from R-851, whose rows covered only the aggregate's path; wrote the rows and
  the pass rule into the readings before drawing them.
