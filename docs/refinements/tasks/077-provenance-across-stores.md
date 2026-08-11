# Provenance across the stores

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)
**Trigger:** the first design that needs a persisted per-turn taint or provenance marker.

It was recorded inside the structured provenance on the `TurnStamp` entry, in its list of what
remains behind the same seam (ADR-0027 addendum deferred). The fragment, verbatim: **provenance across
the stores** (`ScheduledItem` and `SubagentResult` each store the taint bit only, so a fired
task's stamp and a subagent's own readings attribute nothing back to the turn that consumes
them).

## Trail

- 2026-07-16: Opened when structured provenance on the `TurnStamp` landed, as one of the two
  halves that landing could not honestly capture; the area's count went 16 to 17 that day for
  this reason and its sibling.
- 2026-08-06: The replayed-quotation entry named its own trigger as the first design needing a
  persisted per-turn taint or provenance marker, and named this entry as sharing it.
