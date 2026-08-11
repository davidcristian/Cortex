# Session attribution on the dispatcher's turn stamp

**Status:** landed 2026-07-13
**Area:** scheduling
**Origin:** [ADR-0027](../../adr/ADR-0027-turn-provenance.md)

The dispatcher's per-call stamp widened from the lone taint bool to a frozen `TurnStamp`
(`session_id` + `tainted`), built fresh per dispatch from the engine-threaded
`ToolLoopContext.session_id` (the ticker stamps the fired item's stored provenance; a
subagent stamps no session, having none). `schedule_task` fills
`ScheduledItem.session_id` from it, so a created item attributes to its origin chat; the
ticker's fire re-stamps the stored provenance onto its spawn dispatch (honest but
unconsumed today: `spawn_subagents` reads only the taint bit). The stamp is the designed
convergence seam for the ADR-0013/0019 structured-provenance deferrals: source URI/sender
fields join the same object (still deferred there), never a new parallel channel.
Remaining behind the same seam (ADR-0027 deferred): **`SubagentTask` session attribution**
once a subagent-reachable consumer exists, and the **audit line** (`ToolInvocation`)
gaining the stamp when an audit consumer wants per-session queries.
