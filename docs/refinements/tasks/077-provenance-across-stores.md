# Provenance across the stores

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)
**Trigger:** a design that needs a fired schedule item or a subagent result to record the sources the turn behind it read, the way a handoff record stores its own turn's whole ledger.
**Verified:** 2026-09-19

`ScheduledItem` and `SubagentResult` store only the `tainted` flag. Neither records which
sources the turn read, so a consumer of either one cannot tell where the content came from.

What already exists:

- `HandoffRecord` stores the whole `TaintLedger` (`tainted`, `opaque`, `sources`,
  `untrusted_urls`) under the escalating turn's id, and `taint_ledger()` rebuilds it after a
  model swap. The round trip is checked in
  `brain/packages/session/tests/handoff_contract.py`. A settled record expires after an hour.
- `SubagentTask` stores `session_id`, `turn_id` and `item_id`, taken from the spawning
  `TurnStamp` in `spawn.py` and persisted by `cortex_session/tasks.py`. A `SubagentResult` is
  stored under its task id, so one `get_task` gives the turn that spawned it.
- `ScheduledItem` stores `tainted` and a `session_id` taken from the dispatching `TurnStamp`
  in `schedule_tools.py`, so it names the chat but not the turn.

The list of sources is what is still missing. A turn id alone does not tell a consumer what
that turn read.

## History

- 2026-07-16: Opened when structured provenance was added to `TurnStamp`, as one of the two
  halves that change could not cover.
- 2026-08-06: The replayed-quotation entry named the same trigger, the first design needing a
  persisted per-turn taint or provenance marker.
- 2026-09-13: Checked again. The escalation record now stores a turn's whole ledger in Redis,
  so the shared trigger was already used once at a store neither entry named. `ScheduledItem`
  gained `session_id`, which points at the origin chat rather than at the turn. The trigger was
  narrowed to the two rows that still record nothing.
- 2026-09-19: Checked again; the trigger has not fired. The 2026-09-13 correction missed that
  `SubagentTask` has stored `session_id`, `turn_id` and `item_id` since 2026-08-21, so a result
  already names its turn. None of `subagents.py`, `schedule.py`, `schedule_tools.py`,
  `spawn.py`, `handoff.py` or `tasks.py` changed since 2026-09-13, and this entry does not wait
  on [R-074](074-per-provenance-eviction.md), whose subject is memory records.
