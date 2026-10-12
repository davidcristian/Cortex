# A recalled exchange is claimed again with no call

**Status:** done 2026-10-12
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

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

Those rows ran under the earlier text of `schedule_task`'s `at` and `at_time` arguments. On
2026-10-11, on the brain after that change, 20 fresh chats over a fresh store each recalled up to
five earlier exchanges of the same request, and every one of them made a call
([readings](../../readings/recalled-tool-runs.md#results)).

## What to do

Draw the change and rows written in
[recalled-tool-runs.md](../../readings/recalled-tool-runs.md#rows-and-the-rule-written-before-the-first-run)
over a row in which a recalled reply is claimed again. The change, T, needs no schema change: `render_exchange` writes the
turn's runs (`RunLog.runs`, which `TurnEngine` and `BrainPhase` already hold when they call
`record_exchange`) on a line between the message and the reply, and the header in
`turn_context._render_memory_context` says that a run it lists ran in that earlier chat only. A
row stored before T reads as before.

## History

- 2026-10-10: filed from the one-time and daily rows; see also
  [R-834](834-a-reply-claims-a-task-it-never-tried-to-schedule.md).
- 2026-10-11: not reproduced on the brain after the `at` text change: all 20 chats made a call,
  with every turn after the first recalling the earlier exchanges. The change and its pass rule
  are written in the readings before any run of them. The two false claims these rows found are
  another shape: the turn called only `list_scheduled` and copied the recalled reply.
- 2026-10-12: that other shape comes from recall: over a schedule holding the same reminder, 4 of
  50 chats listed and claimed with the earlier exchanges in memory, none of 50 with memory empty,
  and two `list_scheduled` result texts changed nothing
  ([reminder-already-stored.md](../../readings/reminder-already-stored.md)).
- 2026-10-12: done. The change was drawn over that shape, with the store's 20 rows rewritten
  through the new `render_exchange`: 0 false claims in 50 chats against 4 of 50, a new reminder
  still stored in 6 of 6 and a listing question listed only
  ([readings](../../readings/recalled-tool-runs.md#results-over-the-stored-reminder)). It ships
  as [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md) decision 6, which also puts the note
  above a recalled block that holds only tainted memories.
