# The audit trail cannot name the turn a call belonged to

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Every dispatched tool call writes one audit line, and none of them says which conversation, or
which turn, the call was made for. `LoggingAuditSink` prints `tool`, `ok`, `arguments`, `trust`,
`at` and either `result_chars` or `error`, and `ToolInvocation` carries no conversation identity
at all. So the durable record of what this machine did on a user's behalf can be read tool by
tool and never turn by turn, and a failed turn that now names itself
([328](328-a-failed-turn-cannot-name-itself.md)) still cannot be tied to the work that preceded
it.

The shape is cheap and was traced rather than guessed. `TurnStamp` already carries `session_id`,
is built fresh per dispatch from the `ToolLoopContext` (which holds `turn_id`), rides every
`ToolCall` the dispatcher stamps, and was designed to take a field without touching call sites,
which is how `sources` landed. `ToolDispatcher._audited` therefore already holds everything it
needs; what is missing is a field on `ToolInvocation` and a line in the sink that prints it.

**The decision this forces, and the reason it is not a footnote on the change that named the
failure lines.** The dispatcher is shared. A subagent's own tool loop dispatches through it with
a task id where a turn id would go, and the schedule ticker dispatches through it with no
conversation behind the call at all. So the field has to be named for what it means across all
three callers, or the trail acquires a `turn_id` that sometimes names a turn, sometimes a
subagent task, and sometimes nothing. Two options worth weighing:

- **One field, named for the unit of work**, with the ticker's dispatches leaving it empty the
  way `TurnStamp.session_id` already leaves the session empty for an unattributed caller. Cheapest,
  and it makes the trail greppable by one key.
- **A field per kind**, so a subagent's line says which task *and* which turn spawned it. Richer
  for the delegation question ("what did this turn's subagents do?"), and it is the only shape
  that answers it, since a subagent's dispatches otherwise lose the turn entirely.

Whichever is chosen, `session_id` belongs on the line too: the stamp already carries it and the
audit trail is the one record that outlives the process.

## Trail

- 2026-08-20: Opened by the close of
  [328](328-a-failed-turn-cannot-name-itself.md), which asked this question in the same sitting
  and answered it yes, then found the naming decision it forces is the trail's rather than the
  failure line's. Recorded in the ADR-0038 named-turn addendum.
