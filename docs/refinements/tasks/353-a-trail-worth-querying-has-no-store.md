# The trail is now worth querying and has nowhere to be queried

**Status:** open, feature breadth
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
