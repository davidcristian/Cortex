# ToolInvocation audit-line stamp

**Status:** done 2026-08-21
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

Recorded when the dispatcher's `TurnStamp` session attribution was added, as one of two things left
for later: the audit line (`ToolInvocation`) would take the stamp once something wanted per-session
queries.

## History

- 2026-07-13: Recorded as remaining work when the `TurnStamp` session attribution was added.
- 2026-08-21: Closed together with [342](342-the-audit-trail-cannot-name-the-turn.md), which is the
  consumer the trigger named: the audit line now records the chat, the turn and the subagent task
  each dispatch was made for. It takes the stamp's identities rather than the stamp itself, since
  the stamp also holds live handles (a pool, a progress sink, a handoff slot) that a record
  outliving its process must not keep. Recorded in ADR-0009 decision 16, with a pointer at the
  origin.
