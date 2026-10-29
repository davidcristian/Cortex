# A reminder added by a turn in a deleted chat keeps its id

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)
**Verified:** 2026-10-29

`DeleteSession` (`session_rpc.py`) clears the deleted chat as the origin of its scheduled items with
`ScheduleStore.detach_session`, and does not wait for a turn running in that chat (ADR-0021
decision 11). A `schedule_task` call in that turn (`ScheduleTaskTool.invoke`, `schedule_tools.py`)
whose `add` commits after the detach stores an item with the deleted id, so its card offers `open
chat` into a chat that refuses every turn as `session_deleted`. The memory path closes the same
window by reading the deleted set after its row commits (`record_exchange`); the schedule path has
no such read.

Read from the code on 2026-10-29, not reproduced: the overlay tears down the open chat's turn
before it deletes the chat, so the window needs a tool call already past that teardown.

## What to do

1. Reproduce it with a store-level row: an `add` held between the detach's index read and its end,
   or a turn whose `schedule_task` call is delayed past a `DeleteSession`.
2. Decide in ADR-0066 how the add meets a deleted chat: the tool reads `SessionStore.deleted` after
   its `add` and detaches the item, or the add writes `""` for a chat already in the deleted set.

## History

- 2026-10-29: filed from the build of the delete-time detach of a chat's scheduled items.
