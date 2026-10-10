# A recalled exchange is claimed again with no call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-10

With the pgvector memory on, a stored exchange is the user's message and the reply's text, with no
record of the tool runs between them. When a later chat asks the same thing, recall returns that
exchange, and the cortex copies its reply without making the call. On 2026-10-10, five fresh chats
each asked "Remind me tomorrow at 10:00 to check whether the bulb order went out."
([readings](../../readings/schedule-one-time-and-daily.md#results)). The first two called
`schedule_task` and stored a reminder. In the last three, the `cortex.memory.recall` line listed
the first two exchanges as hits (`tainted: false`); each of these turns made no call and replied
"OK. I've set a reminder for you ... tomorrow, October 11th, at 10:00 AM", and nothing was stored.

This is the shape [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md) fixed for a chat's own
history, reached through recall instead: replay covers stored messages, and a recalled memory is
system context, so it has no runs to replay.

## What to do

Decide how a recalled exchange shows that its reply came from a tool run, or that it must not be
taken as done: for example, store the turn's run names with the memory row and render them in
the recall context, or render a recalled reply as past text that says no action is repeated. A
change to what the model reads is measured first: the five-chat row above, with the memory rows
of each chat kept, counting turns that claim a reminder with no `schedule_task` run.

## History

- 2026-10-10: filed from the one-time and daily rows; see also
  [R-834](834-a-reply-claims-a-task-it-never-tried-to-schedule.md).
