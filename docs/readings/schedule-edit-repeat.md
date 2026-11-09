# Readings: an edit that sets `repeat` on a one-time reminder

Whether the cortex sets `repeat` to true on an `edit_scheduled` call the person did not ask to
repeat, which turns a one-time item into a rule. `once_kept` in
`brain/packages/core/src/cortex_core/schedule_edit_at.py` refuses `at_time` on a one-time item
unless the call sets `repeat`, and its result says to call again with `repeat` set to true only if
the person asked for it to repeat. Read with
[ADR-0065](../adr/ADR-0065-wall-clock-schedule-times.md) and
[overlay-corrections-flows.md](overlay-corrections-flows.md#a-one-time-item-given-at_time).

## The rig

**2026-11-09**, the shared `cortexn17` stack: the resident cortex (gemma-4-12B, text only,
context 16384), Redis schedules with `CORTEX_SCHEDULE_TZ=Europe/Berlin`, the stack brain built
from `1cd9e97fe`. The draws run on Monday 2026-11-09 before dawn, so Friday is 2026-11-13 and
Tuesday is 2026-11-10. Each draw is one chat: a first turn stores the item, then the follow-up
moves it, every card approved. The calls are read from the brain's `tool.invocation` log lines,
the item from Redis by its `session_id`, and every item of the draw is deleted before the next
one. Row m2 was added after m1's draws and before its own, because m1 never reached the refusal,
while the same follow-up reached it in the earlier rows.

## The row and the rule, written before the first draw

| Row | First turn | Follow-up | Draws | Pass when |
| --- | --- | --- | --- | --- |
| m1 | `Remind me on Friday at 10 to go to the dentist.` | `Move my dentist reminder to Tuesday at 15:00.` | 6 | one item, one time, due 2026-11-10 15:00 Berlin |
| m2 | `Remind me on Friday at 10 to go to the dentist.` | `Change it to 3 in the afternoon.` | 6 | one item, one time, due 2026-11-13 15:00 Berlin |

**Counts.** The follow-up's `edit_scheduled` calls that set `repeat` to true, each one unasked
since neither turn names a repeat; how many follow-ups reached the `once_kept` refusal; and how
many of those retried with `repeat` set to true.

**Rule.** A brain-appended note over an edit that turns a one-time item into a weekly rule ships
whatever the counts: it is shown only when that edit ran, and then it states what the store holds,
the way the daily note closes an edit that makes a one-time item daily. A null result is 0 of 6
calls with `repeat`; the note still ships, and the count says the form is rare. One or more
retries with `repeat` after the refusal, in a draw that never asked for a repeat, files a task to
change the refusal's text, since a result the model reads must not lead it to a change the person
did not ask for.

## Results

Drawn at 04:38 to 04:45 (chats `s10m-1` to `s10m-6` and `s10n-1` to `s10n-6`, records
`rows.jsonl`, `rows2.jsonl`, `calls.txt` and `calls2.txt` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot10/`).
The SM clock read 0.57 of `clocks.max.sm` throughout.

| Row | Passed | Calls with `repeat` | Reached the refusal | Retried with `repeat` |
| --- | --- | --- | --- | --- |
| m1 | 6 of 6 | 0 of 6 | 0 of 6: every first edit passed `at` | none to retry |
| m2 | 6 of 6 | 0 of 10 | 4 of 6, each a first edit with `at_time` 15:00 alone | 0 of 4: each retried with `at` |

Every m1 edit passed `at` 2026-11-10T15:00 with or without the `+01:00` offset, after a
`list_scheduled`. No draw set `repeat`, so the form is rare on this message; the note ships under
the rule, shown only when an edit with `repeat` true, `at_time` and a day selector ran. With the
earlier rows in [overlay-corrections-flows.md](overlay-corrections-flows.md#a-one-time-item-given-at_time),
the refusal was reached in 8 follow-ups that asked for no repeat and none retried with `repeat`,
so its text files no task.

## A live edit asked to repeat

On the stack brain rebuilt from the tree with the note, at 04:55 (chat `s10v-1`, record `live.jsonl`
in the same directory, SM clock 0.57 of `clocks.max.sm`): `Make that dentist reminder repeat every
Tuesday at 15:00 instead.` over the Friday item first passed `at_time` and `on_days` alone, was
refused, and retried with `repeat` true. The item became a rule on Tuesdays at 15:00, and the reply
`It will now repeat every Tuesday at 15:00.` closed with `MADE_REPEATING_NOTE`. `names_repeat` does
not read a bare `repeat`, so the note repeats what the reply says, filed as
[task 1085](../refinements/tasks/1085-a-reply-saying-it-will-repeat-still-gets-the-repeat-note.md).
