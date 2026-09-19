# The recall trail has no store an operator can query

**Status:** open, optional feature
**Area:** memory
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-17

`RecallAuditSink` (`brain/packages/core/src/cortex_core/ports.py:209`) has one adapter,
`LoggingRecallSink` in `cortex_memory/audit.py`, and the fake `RecordingRecallSink`.
`memory_builders.recall_audit_from_config` attaches it when `CORTEX_MEMORY_RECALL_AUDIT` is on, so
the recall trail lives only as long as the container's log driver keeps it. The tool audit trail
gained a file adapter behind its unchanged port (`JsonLinesAuditSink`, ADR-0009 decision 18), and
the same design would serve this one: a second adapter appending one JSON object per recall, tee'd
behind the logging sink.

It was not done in the same change because the record differs. `RecallAudit` includes the ranking,
the rank basis and the dropped candidates with a count of what the bound left out, so the file needs
its own decision about which fields the line prints and how the formatter cuts the dropped list, and
its own contract suite over the fake and the file. The setting differs too: recall audit is a
boolean today, where the tool trail takes a path, so the config needs either a path beside the flag
or a path that implies it.

**What would be built.** A `JsonLinesRecallSink` in `cortex_memory`, reusing the value rules in
`cortex_tools/audit_file.py` (`durable_value`) once they move to a package both can import, a
`CORTEX_MEMORY_RECALL_AUDIT_FILE` setting, a contract suite over the fake and the file, and the
memory runbook's reading instructions. In the same change, correct the first sentence of the
`ToolAuditSink` docstring in `cortex_core/ports_tools.py`, which still says adapters log structured
lines.

## History

- 2026-09-17: filed by the close of
  [353](353-a-trail-worth-querying-has-no-store.md), which built the tool trail's file half and left
  this one for its different record. Recorded in ADR-0009 decision 18.
