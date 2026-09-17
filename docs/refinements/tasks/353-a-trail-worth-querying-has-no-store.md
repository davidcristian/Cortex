# The trail is now worth querying and has nowhere to be queried

**Status:** landed 2026-09-17
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`ToolAuditSink` has exactly one adapter, `LoggingAuditSink`, so the audit trail is a stream of
`logging` records and nothing else. That was proportionate while a line said only which tool ran:
an operator greps a tool name and reads what is around it. It is less proportionate now that a line
names the chat, the turn and the subagent task it belongs to, because those fields make a real
query expressible ("everything this turn did", "everything this delegate did", "every gated call
this chat ever denied") against a substrate that answers none of them. The retention policy is the
container's log driver, and under the default rendering the answer is a `grep` over text.

The shape is a second adapter behind the unchanged port, which is what the port is for. Postgres is
already in the stack for memory (ADR-0008) and its init script is where a table would go; a
file-backed JSON-lines sink is the cheaper half and buys retention without a query language. The
open questions are not the wiring but the policy: how long a trail is kept, whether `arguments`
belong in a durable store at the same fidelity they are printed at (the bound that cuts a rendered
value is a formatter's, so a store would keep what the line does not), and whether a failed write
to a durable sink may ever fail a dispatch, which the logging sink never had to answer.

Nothing needs this today: the machine serves one user, and the reading the trail was widened for is
one an operator does by eye. It is written down because the widening is what made the gap visible.

## Trail

- 2026-08-21: Opened by the close of
  [342](342-the-audit-trail-cannot-name-the-turn.md), which gave the trail the identities that make
  it queryable. Recorded in the ADR-0009 named-work addendum.
- 2026-09-13: re-derived and still open. `ToolAuditSink` still has exactly one adapter,
  `cortex_tools.audit.LoggingAuditSink`, with `RecordingAuditSink` in `cortex_core.fakes` being
  the fake; the line still carries the session, turn, task, item and call ids off the dispatch
  stamp, so the queries this entry names are still expressible and still unanswerable; and
  retention is still the container's log driver. One thing widened. The brain now writes a second
  audit trail, the recall trail, and `RecallAuditSink` is in the same state: one adapter,
  `LoggingRecallSink`, chosen by a config flag in `memory_builders.recall_audit_from_config`. So
  a durable sink is now a policy decision over two ports rather than one, and the three open
  questions above, on retention, on the fidelity a store keeps an argument at, and on whether a
  failed durable write may fail the work it audits, are asked of both.
- 2026-09-17: landed as the file half, `JsonLinesAuditSink` in `cortex_tools/audit_file.py`,
  behind the port as it stood, off unless `CORTEX_TOOLS_AUDIT_FILE` names a file, and recorded in
  the ADR-0009 durable-trail addendum. The three questions were answered there: retention is the
  operator's, since the sink reopens the path per record and a `mv` rotates it; the file keeps
  exactly what the log line prints, the formatter's cut and credential rules included, rather
  than full arguments; and a failed append is logged as a `tool.audit.gap` warning and never
  fails the dispatch, because the dispatcher awaits its sink unguarded and the log line is written
  first. The Postgres half was not built, a table tying the trail to the optional memory
  override. The port gained a shared list over the fake, the file sink and a tee of the two. The
  recall trail's half is
  [683](683-the-recall-trail-has-no-store.md), and a secret-named argument key, which both trails
  print, is [684](684-a-secret-named-argument-prints-on-both-audit-trails.md).
