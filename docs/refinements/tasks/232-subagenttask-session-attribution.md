# SubagentTask session attribution

**Status:** landed 2026-08-21
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

Recorded inside the entry for the dispatcher's `TurnStamp` session attribution, which landed the
stamp itself and named this as one of the two things left behind the same seam.

Remaining behind the same seam (ADR-0027 deferred): **`SubagentTask` session attribution**
once a subagent-reachable consumer exists.

That entry also records the state the attribution is in today: a subagent stamps no session, having
none, and the ticker's fire re-stamps the stored provenance onto its spawn dispatch (accurate but
unconsumed today: `spawn_subagents` reads only the taint bit).

## Trail

- 2026-07-13: Recorded as remaining when the `TurnStamp` session attribution landed.
- 2026-08-21: Landed with the close of [342](342-the-audit-trail-cannot-name-the-turn.md).
  `SubagentTask` gained `session_id` and `turn_id`, written by `spawn_subagents` off the dispatch
  stamp and read back by the attempt, so a delegated tool call is audited under the chat and the
  turn that asked for it. It rides the record rather than a parameter because a subagent is a
  stateless function over the store, which is also why the ticker's fire (which stamps a chat and no
  turn) now reaches the trail correctly. Recorded in the ADR-0009 named-work addendum, with a
  pointer at the origin.
