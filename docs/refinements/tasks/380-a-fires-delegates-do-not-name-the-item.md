# A scheduled item's delegates do not name the item that started them

**Status:** done 2026-08-23
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`TurnStamp.item_id` names the scheduled item a dispatch was made for, and the audit line prints it,
but only the ticker's own `spawn_subagents` dispatch has one. The subagent that dispatch spawns
runs its own tool loop through the same dispatcher, and every call it makes names the chat and its
task and no item, because `item_id` stops at the spawn call.

That breaks the reading the field was added for. A scheduled task's actual work is whatever its
subagent did, so `grep item_id=t1` reaches the one line that says the item ran and none of the
lines that say what running it caused. The chat is on all of them and is not a filter: one chat
schedules many items, and a scheduled item's delegate can be running while a conversation in that
same chat is dispatching too. The task id does select the delegate, but it is created by `uuid4`
inside the spawn tool, printed on no other line, and stored in a record that expires in an hour.

The fix is the shape ADR-0009 decision 16 uses for `session_id` and `turn_id`: `SubagentTask` gains
the identity, `SpawnSubagentsTool` writes it off the dispatch stamp, `SubagentAttempt` reads it
back into its `ToolLoopContext`, and `_stamp` puts it on every dispatch the delegate makes. It is a
value rather than a live handle, so it belongs on the stored task and not in a parameter: a
subagent is a stateless function over the `TaskStore`, and an attribution that lived only in a
keyword argument would be lost on every re-read. The cost is the Redis codec and its contract test.

Worth checking while doing it: whether the four work identities on `ToolLoopContext` want to travel
as one value rather than as four keywords.

## History

- 2026-08-22: Opened by the close of [352](352-a-dispatch-names-no-call.md), which put the
  scheduled item on the ticker's own dispatch and stopped there. Recorded in ADR-0009 decision 16.
- 2026-08-23: Done in the shape this entry proposed, at every step where it said: `SubagentTask`
  gained `item_id`, `SpawnSubagentsTool` writes it off the dispatch stamp, the Redis codec
  round-trips it, `PlacedAttempt` reads it back into its `ToolLoopContext`, and `_stamp` puts it on
  every dispatch the delegate makes. The cost it named was the codec and its contract test, and
  that held. The one question it left open, whether a task stored without the field should read
  back as unattributed, is answered no: the key is required like both neighbours, because `""`
  already means no item and a defaulted read would make a dropped attribution indistinguishable
  from an absence the record was told about. The bundle it asked about is declined, and the count
  in the question is the correction: there were three work identities on `ToolLoopContext` and this
  makes four. They stay four keywords, on the criterion the deep tier's own bundle was built on,
  which is that parts belong in one value when they are meaningless apart. These four are the
  opposite: every combination of present and absent is a caller this tree really has, so a bundle
  would exclude no invalid state, and the same four are deliberately flat on `TurnStamp` and on the
  audit record, so one would cost a translation at each end. Verified against a real Redis and the
  shipped formatter, where a schedule-shaped dispatch put `item_id=r-live-1` on the ticker's line
  and on its delegate's. Two entries opened,
  [394](394-the-fired-item-has-two-spellings-in-the-logs.md) for the ticker's own lines writing the
  same id as `reminder_id`, and
  [395](395-a-work-identity-is-copied-by-hand-at-every-hop.md) for the six hand-written copies a
  work identity crosses.
