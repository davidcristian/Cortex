# Provenance across the stores

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)
**Trigger:** a design that needs a fired schedule item or a subagent result to carry the sources the turn behind it read, the way a handoff record carries its own turn's whole ledger.
**Verified:** 2026-09-19

It was recorded inside the structured provenance on the `TurnStamp` entry, in its list of what
remains behind the same seam (ADR-0027 addendum deferred). The fragment, verbatim: **provenance across
the stores** (`ScheduledItem` and `SubagentResult` each store the taint bit only, so a fired
task's stamp and a subagent's own readings attribute nothing back to the turn that consumes
them).

**Corrected 2026-09-13: one store carries a turn's provenance today, and one of the two named rows
gained an identity.** `HandoffRecord` persists `tainted`, `opaque`, `sources` and `untrusted_urls`,
which is the whole `TaintLedger`, under the escalating turn's own id, and `taint_ledger()` rebuilds
it on the far side of a model swap with the handoff store's contract test pinning the round trip
(`brain/packages/session/tests/handoff_contract.py`). So the trigger as first worded, the first
design needing a persisted per-turn taint or provenance marker, fired when the swap needed one, and
the answer was built at that store alone. The two rows this entry names are where it left them.
`SubagentResult` carries `task_id`, `output`, `ok`, `detail` and `tainted`. `ScheduledItem` carries
`tainted` and a `session_id` taken from the dispatching `TurnStamp` in `schedule_tools.py`, so a
fired item names the chat it was created in while naming neither the turn nor the sources that turn
read. The trigger above now asks for what is missing rather than for what has been built.

## Trail

- 2026-07-16: Opened when structured provenance on the `TurnStamp` landed, as one of the two
  halves that landing could not honestly capture; the area's count went 16 to 17 that day for
  this reason and its sibling.
- 2026-08-06: The replayed-quotation entry named its own trigger as the first design needing a
  persisted per-turn taint or provenance marker, and named this entry as sharing it.
- 2026-09-13: Re-derived, and the entry was wrong in one direction and right in the other. It was
  filed saying the stores carry the taint bit alone, and since then the escalation record landed
  carrying a turn's whole ledger through Redis, so the general trigger this entry shared with the
  replayed-quotation entry has been spent once at a store neither entry named. `ScheduledItem`
  gained `session_id` from the dispatching stamp in the same period, which is attribution to the
  origin chat and not to the turn. Both corrections are written above and the trigger is narrowed to
  the two rows that still attribute nothing, which is what is left of the entry.
- 2026-09-19: Re-derived, and the trigger has not fired, but its subagent half was true the day it
  was written. `SubagentTask` has carried `session_id`, `turn_id` and `item_id` since 2026-08-21,
  taken from the spawning `TurnStamp` in `spawn.py` and persisted by the Redis task store
  (`cortex_session/tasks.py`), and a `SubagentResult` is stored under its task's id, so a result
  already names the turn that spawned it through one `get_task`. The correction above lists the
  result's fields and misses that. What neither row reaches is what the turn read: the task keeps
  only `tainted`, and nothing keyed by a turn id persists a `TaintLedger` except the handoff record
  of a turn that escalated, whose settled record expires after an hour. A `ScheduledItem` still
  names its chat and not its turn. The trigger now asks for the sources, which is what a consumer
  of provenance would read and what a turn id alone does not give it. None of `subagents.py`,
  `schedule.py`, `schedule_tools.py`, `spawn.py`, `handoff.py` or `tasks.py` has changed since
  2026-09-13, and this entry does not wait on [R-074](074-per-provenance-eviction.md), whose
  subject is memory records.
