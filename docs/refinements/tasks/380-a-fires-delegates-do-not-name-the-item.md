# A fire's delegates do not name the item that fired them

**Status:** open, actionable
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`TurnStamp.item_id` now names the scheduled item a dispatch was made for, and the audit line
prints it, but only the ticker's own `spawn_subagents` dispatch carries one. The subagent that
dispatch spawns runs its own tool loop through the same dispatcher, and every call it makes names
the chat and its task and no item, because `item_id` stops at the spawn call.

The reading this leaves broken is the one the field was added for. A fired task's actual work is
whatever its subagent did, so `grep item_id=t1` reaches the one line that says the item fired and
none of the lines that say what firing it caused. The chat is on all of them and is not a filter:
one chat schedules many items, and a fire's delegate can be running while a conversation in that
same chat is dispatching too. The task id does select the delegate, but it is minted by `uuid4`
inside the spawn tool, printed on no other line, and stored in a record that expires in an hour,
which is the argument the named-work addendum already made for why a task id alone is not an
answer a reader can reach.

The shape is the one that addendum landed for `session_id` and `turn_id`: `SubagentTask` gains
the identity, `SpawnSubagentsTool` writes it off the dispatch stamp, `SubagentAttempt` reads it
back into its `ToolLoopContext`, and `_stamp` puts it on every dispatch the delegate makes. It is
a value rather than a live handle, so it belongs on the stored task and not in a parameter: a
subagent is a stateless function over the `TaskStore`, and an attribution living only in a keyword
is the one fact about the work that a re-read could not recover. The cost is the Redis codec and
its contract test, which is what made this a task of its own rather than a line in the change that
introduced the field.

Worth checking while doing it: whether the four work identities on `ToolLoopContext` want to
travel as one value rather than as four keywords, since the next one to arrive will be the fifth
argument spelled the same way.

## Trail

- 2026-08-22: Opened by the close of
  [352](352-a-dispatch-names-no-call.md), which put the fired item on the ticker's own dispatch
  and stopped there. Recorded in the ADR-0009 named-call addendum.
