# SubagentTask session attribution

**Status:** done 2026-08-21
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

Recorded when the dispatcher's `TurnStamp` session attribution was added, as one of two things left
for later: `SubagentTask` would take the session id once something read it.

## History

- 2026-07-13: Recorded as remaining work when the `TurnStamp` session attribution was added.
- 2026-08-21: Closed together with [342](342-the-audit-trail-cannot-name-the-turn.md).
  `SubagentTask` gained `session_id` and `turn_id`, written by `spawn_subagents` from the dispatch
  stamp and read back by the attempt, so a delegated tool call is audited under the chat and the
  turn that asked for it. They are stored on the record rather than passed as a parameter, because
  a subagent is a stateless function over the store, which is also why the ticker's fire, which
  knows a chat but no turn, now reaches the audit trail correctly. Recorded in ADR-0009 decision
  16, with a pointer at the origin.
