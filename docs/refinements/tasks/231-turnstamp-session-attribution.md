# Session attribution on the dispatcher's turn stamp

**Status:** done 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

The dispatcher's per-call stamp grew from a single taint flag to a frozen `TurnStamp` (`session_id`
plus `tainted`), built fresh per dispatch from `ToolLoopContext.session_id`. The ticker stamps the
fired item's stored provenance; a subagent stamps no session, having none. `schedule_task` fills
`ScheduledItem.session_id` from the stamp, so a created item is attributed to its origin chat, and
the ticker re-stamps the stored provenance onto its spawn dispatch, which is accurate but unused
today because `spawn_subagents` reads only the taint flag.

The stamp is where the structured provenance deferred at ADR-0013 and ADR-0019 is meant to
converge: source URI and sender fields join the same object instead of a second channel. Two things
were left for later, each in its own entry: `SubagentTask` session attribution, and the
`ToolInvocation` audit line.
