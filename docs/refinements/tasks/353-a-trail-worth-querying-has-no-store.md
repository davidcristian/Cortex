# The audit trail is worth querying and has nowhere to be queried

**Status:** done 2026-09-17
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`ToolAuditSink` had exactly one adapter, `LoggingAuditSink`, so the audit trail was a stream of
`logging` records and nothing else. That was proportionate while a line said only which tool ran.
It is less so now that a line names the chat, the turn and the subagent task it belongs to, because
those fields make a real query expressible ("everything this turn did", "everything this delegate
did", "every denied call this chat ever made") against something that answers none of them.
Retention is the container's log driver, and under the default rendering the answer is a `grep`
over text.

The fix is a second adapter behind the unchanged port. Postgres is already in the stack for memory
(ADR-0008) and its init script is where a table would go; a file-backed JSON-lines sink is the
cheaper half and gives retention without a query language. The open questions are policy rather
than wiring: how long a trail is kept, whether `arguments` belong in a durable store at the
fidelity they are printed at (the bound that cuts a rendered value is a formatter's, so a store
would keep what the line does not), and whether a failed write to a durable sink may ever fail a
dispatch.

## History

- 2026-08-21: Opened by the close of [342](342-the-audit-trail-cannot-name-the-turn.md), which gave
  the trail the identities that make it queryable. Recorded in ADR-0009 decision 16.
- 2026-09-13: Checked again and still open. `ToolAuditSink` still has exactly one adapter,
  `cortex_tools.audit.LoggingAuditSink`, with `RecordingAuditSink` in `cortex_core.fakes` being the
  fake; the line still has the session, turn, task, item and call ids off the dispatch stamp; and
  retention is still the container's log driver. One thing widened: the brain now writes a second
  audit trail, the recall trail, and `RecallAuditSink` is in the same state, one adapter,
  `LoggingRecallSink`, chosen by a config flag in `memory_builders.recall_audit_from_config`. So a
  durable sink is a policy decision over two ports rather than one.
- 2026-09-17: Built as the file half, `JsonLinesAuditSink` in `cortex_tools/audit_file.py`, behind
  the port as it stood, off unless `CORTEX_TOOLS_AUDIT_FILE` names a file, and recorded in ADR-0009
  decision 18. The three questions were answered there: retention is the operator's, since the sink
  reopens the path per record and a `mv` rotates it; the file keeps exactly what the log line
  prints, the formatter's cut and credential rules included, rather than full arguments; and a
  failed append is logged as a `tool.audit.gap` warning and never fails the dispatch, because the
  dispatcher awaits its sink unguarded and the log line is written first. The Postgres half was not
  built, a table connecting the trail to the optional memory override. The port gained a shared
  check list over the fake, the file sink and a tee of the two. The recall trail's half is
  [683](683-the-recall-trail-has-no-store.md). A secret-named key inside `arguments` is withheld on
  both trails alike (ADR-0009 decision 17).
