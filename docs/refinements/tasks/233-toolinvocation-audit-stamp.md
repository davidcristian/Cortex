# ToolInvocation audit-line stamp

**Status:** landed 2026-08-21
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

Recorded inside the entry for the dispatcher's `TurnStamp` session attribution, which landed the
stamp itself and named this as one of the two things left behind the same seam.

Remaining behind the same seam (ADR-0027 deferred): the **audit line** (`ToolInvocation`)
gaining the stamp when an audit consumer wants per-session queries.

## Trail

- 2026-07-13: Recorded as remaining when the `TurnStamp` session attribution landed.
- 2026-08-21: Landed with the close of
  [342](342-the-audit-trail-cannot-name-the-turn.md), which is the consumer this trigger named: the
  audit line now carries the chat, the turn and the subagent task each dispatch was made for. It
  takes the stamp's identities rather than the stamp, since the stamp also carries live handles (a
  pool, a progress sink, a handoff slot) that a record outliving its process must not hold.
  Recorded in the ADR-0009 named-work addendum, with a pointer at the origin.
