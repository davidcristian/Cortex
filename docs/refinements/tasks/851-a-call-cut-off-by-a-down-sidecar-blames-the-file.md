# A call cut off by a down sidecar blames the file

**Status:** done 2026-10-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

When a sidecar stops during a call, the text the model reads for that call misleads it. Under
`CORTEX_TOOLS_ON_UNAVAILABLE=fail` it is the `ToolError` text `MCP sidecar unavailable`: with
`mcp-filesystem` killed during `read_text_file`, the model replied that "the file `choir-rota.txt`
appears to be unavailable or inaccessible as the content returned is "MCP sidecar unavailable"",
blaming the file and quoting the error
([readings](../../readings/store-and-sidecar-outages.md#the-filesystem-sidecar)). Under `skip`, the
default, it is the same text with one sidecar configured; with two or more it is
`unknown tool 'read_text_file'`, because `AggregateToolRegistry.invoke` routes by
listing every registry again and `SkipUnavailableToolRegistry` now lists nothing; in a probe row the
model retried unknown tools and wrote "Actually, I'll try `read_text_file` again." until the reply
stopped at the length limit ([readings](../../readings/tool-call-cut-off.md#results)). A listing
that finds the sidecar down sends a status naming it (ADR-0009 decision 8); a call cut off
mid-flight does not.

## Reproduce

On the GPU stack with the file sidecar, ask to read a file, `docker pause` the `mcp-filesystem`
container once the brain audits a `list_directory` call, and `docker kill` it 8 s later.

## What to do

The aggregate now returns `SERVER_DOWN_MSG`, naming the server, for a tool a stopped server last
listed, as the [rule decided on the code](../../readings/tool-call-cut-off.md#a-rule-decided-on-the-code)
calls for. Run the next rows written there, which decide the candidate's clause that the text says
nothing about the file. A `forgoing` status naming the server when such a call fails is decided
apart from the rows.

## History

- 2026-10-13: filed when the down-sidecar listing was changed to answer the turn without the
  sidecar's tools; this half, the call already running, was left as it is.
- 2026-10-13: wrote the rows, the candidate's text and the pass rule into the readings; a probe
  row under `skip` found the `unknown tool` text and a reply that looped to the length limit,
  filed as R-853.
- 2026-10-13: ran the 5 baseline rows: 2 quote the error or loop, under the rule's 3, so the
  defect does not reproduce with this prompt and the candidate was not run. Next: rows with a
  different prompt, written before they are drawn, as the rule says.
- 2026-10-14: checked the premise against the code: `unknown tool` comes only from the
  aggregate, with two or more sidecars; one sidecar reads `MCP sidecar unavailable`. Wrote a rule
  decided on the code for an accurate text, and the next rows, into the readings.
- 2026-10-14: the skip wrapper keeps the names of its last good listing, and the aggregate
  returns `SERVER_DOWN_MSG` for one of them before it reports an unknown tool.
- 2026-10-14: ran the next rows on the new text: 0 of 5 blame the file, quote the error, loop or
  invent, so the candidate's clause is not added. Declined the `forgoing` status for a call that
  fails during a turn: the body shows that call's failed chip, the reply named the server in 5 of
  5 rows, and the next turn's listing sends the status. Filed the one sidecar path, which keeps
  `MCP sidecar unavailable`, as R-856.
