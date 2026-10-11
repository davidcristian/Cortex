# A recalled exchange is claimed again with no call

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** a row on the shipped stack in which a turn that recalled an earlier exchange makes no
call and copies the recalled reply's claim.
**Verified:** 2026-10-11

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

When the trigger fires, run the change and rows written in
[recalled-tool-runs.md](../../readings/recalled-tool-runs.md#rows-and-the-rule-written-before-the-first-run)
against the row that fired it. The change, T, needs no schema change: `render_exchange` writes the
turn's runs (`RunLog.runs`, which `TurnEngine` and `BrainPhase` already hold when they call
`record_exchange`) on a line between the message and the reply, and the header in
`turn_context._render_memory_context` says that a run it lists ran in that earlier chat only. A
row stored before T reads as before, which is what R3 measures.

## History

- 2026-10-10: filed from the one-time and daily rows; see also
  [R-834](834-a-reply-claims-a-task-it-never-tried-to-schedule.md).
- 2026-10-11: not reproduced on the brain after the `at` text change: all 20 chats made a call,
  with every turn after the first recalling the earlier exchanges. The change and its pass rule
  are written in the readings before any run of them, and the task waits for a row that shows
  the shape again. The two false claims these rows found are another shape, filed as
  [R-839](839-a-reply-says-it-set-a-reminder-it-only-found-listed.md).
