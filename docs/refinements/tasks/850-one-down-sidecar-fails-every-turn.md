# One down sidecar fails every turn

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-13

Under the default `CORTEX_TOOLS_ON_UNAVAILABLE=fail`, a stopped `mcp-filesystem` made every turn
fail before inference, including a question that needs no file. `stream_tool_loop` in
`tool_loop.py` calls `describe_tools` first, the `ToolError` from `ReconnectingMcpToolRegistry`
leaves the turn, and `converse_stream.py` logs `unexpected failure handling a turn` and sends the
gRPC error event `internal: MCP sidecar unavailable`, which the overlay shows as the reply beside a green
link dot ([readings](../../readings/store-and-sidecar-outages.md#the-filesystem-sidecar)). Until
2026-10-13 the [tools runbook](../../runbooks/tools-mcp.md) said the model sees an `is_error`
result instead.

The same text reaches the model when a call fails: a sidecar killed during `read_text_file` gave a
reply saying the file "appears to be unavailable" and quoting "MCP sidecar unavailable". The
sidecar container also reports `Up` 3 to 6 s before it listens, while it runs `npm install`.

## Reproduce

`docker kill` the `mcp-filesystem` container of a stack with the file sidecar and send "What key is
the Bach cello suite number six in?".

## What to do

Decide what a down sidecar costs a turn under `fail`: a typed error event with a plain sentence and
a code the overlay can tell from a brain fault, or the skip behaviour as the default (ADR-0009
decision 8 states `fail`). A change to the text the model reads needs rows and a pass rule first.

## History

- 2026-10-13: filed from the outage flows; the runbook sentence was corrected the same day.
