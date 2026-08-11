# SubagentTask session attribution

**Status:** open, dead until a consumer
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)
**Trigger:** a subagent-reachable consumer of the attribution exists.

Recorded inside the entry for the dispatcher's `TurnStamp` session attribution, which landed the
stamp itself and named this as one of the two things left behind the same seam.

Remaining behind the same seam (ADR-0027 deferred): **`SubagentTask` session attribution**
once a subagent-reachable consumer exists.

That entry also records the state the attribution is in today: a subagent stamps no session,
having none, and the ticker's fire re-stamps the stored provenance onto its spawn dispatch
(honest but unconsumed today: `spawn_subagents` reads only the taint bit).

## Trail

- 2026-07-13: Recorded as remaining when the `TurnStamp` session attribution landed.
