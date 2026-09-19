# The audit trail cannot name the turn a call belonged to

**Status:** done 2026-08-21
**Area:** tools-mcp
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

Every dispatched tool call writes one audit line, and none says which conversation, or which turn,
the call was made for. `LoggingAuditSink` prints `tool`, `ok`, `arguments`, `trust`, `at` and
either `result_chars` or `error`, and `ToolInvocation` has no conversation identity at all. So the
durable record of what this machine did on a user's behalf can be read tool by tool and never turn
by turn.

The change is small. `TurnStamp` already has `session_id`, is built fresh per dispatch from the
`ToolLoopContext` (which holds `turn_id`), goes on every `ToolCall` the dispatcher stamps, and was
designed to take a field without touching call sites. What is missing is a field on
`ToolInvocation` and a line in the sink that prints it.

The decision it forces is naming. The dispatcher is shared: a subagent's own tool loop dispatches
through it with a task id where a turn id would go, and the schedule ticker dispatches through it
with no conversation behind the call. So the field has to be named for what it means across all
three callers. Either one field named for the unit of work, with the ticker's dispatches leaving it
empty, which is cheapest and makes the trail findable by one key; or a field per kind, so a
subagent's line says which task and which turn spawned it, which is the only form that answers what
a turn's subagents did. Either way `session_id` belongs on the line too.

## History

- 2026-08-20: Opened by the close of [328](328-a-failed-turn-cannot-name-itself.md), which asked
  this question, answered it yes, and found the naming decision belongs to the trail rather than
  the failure line. Recorded in ADR-0046 decision 9.
- 2026-08-21: Fixed as a field per kind, argued in ADR-0009 decision 16: the line has `session_id`,
  `turn_id` and `task_id`, each left off when the dispatch had none. The one generic field was
  rejected because a subagent's task id is printed on no other line in the tree and expires from
  its store in an hour, so it would name work that resolves against nothing a reader can reach.
  This entry's "already holds everything it needs" was half right: the dispatcher does hold the
  stamp on every path, and the stamp held no turn id, that living on the `ToolLoopContext` which
  builds it. So it cost a field on `TurnStamp`, an attribution on the stored `SubagentTask` (which
  closed [232](232-subagenttask-session-attribution.md) and
  [233](233-toolinvocation-audit-stamp.md), both waiting for exactly this consumer), and a derived
  `unit_id` on the loop context so a subagent's own messages stay grouped under its task. Opened
  [352](352-a-dispatch-names-no-call.md), the call id that reaches no line, and
  [353](353-a-trail-worth-querying-has-no-store.md), the trail that is now worth querying and has
  nowhere to be queried.
