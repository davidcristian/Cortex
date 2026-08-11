# ToolInvocation audit-line stamp

**Status:** open, dead until a consumer
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)
**Trigger:** an audit consumer wants per-session queries.

Recorded inside the entry for the dispatcher's `TurnStamp` session attribution, which landed the
stamp itself and named this as one of the two things left behind the same seam.

Remaining behind the same seam (ADR-0027 deferred): the **audit line** (`ToolInvocation`)
gaining the stamp when an audit consumer wants per-session queries.

## Trail

- 2026-07-13: Recorded as remaining when the `TurnStamp` session attribution landed.
