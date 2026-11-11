# The unscheduled claim note shows under a reminder status or a memory update

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-11

`claims_scheduled` in `schedule_claim.py` reads two forms as a schedule claim since 2026-11-11:
`_fires_now` (a reminder that `now goes off`, `fires`, `rings` or `is now at` a time) and an
object pronoun after an update verb, read against the person's last message. Neither form looks
at what the turn did. On a turn with no successful scheduling call, each reply below reads as a
claim, so `UNSCHEDULED_CLAIM_NOTE` ends it with "Nothing was scheduled in this turn ... Ask again
to schedule it.":

| Person's last message | Reply |
| --- | --- |
| `When does my dentist reminder go off now?` | `Your dentist reminder now goes off at 9:30.` |
| `What time is my dentist reminder?` | `Your dentist reminder is now at 9:30, since you moved it yesterday.` |
| `List my reminders` | `Your alarm now rings at 7:00 every weekday.` |
| `My dentist reminder is fine. Please update my address in memory to 12 Oak Street.` | `I've updated it.` |
| `Remember that my reminder app is TickTick, update my notes about it` | `I've updated it in memory.` |

The check was a call of `claims_scheduled(reply, said=(message,))` on each pair in the brain
venv; no live draw has shown either form. The note's safe direction is to show, so these are on
its safe side, but its last sentence asks for a new store of a reminder that is already stored,
which can make a duplicate. The first three are a status read after `list_scheduled`; the
readings record the first one as a known cost of `_fires_now`
([readings](../../readings/schedule-change-request.md#a-new-time-with-no-update-verb-2026-11-11)).

## What to do

1. Count first: move a reminder in one turn, then ask `When does my plant reminder go off now?`
   in the next, at least eight times on the stack, and count the replies that end with the note.
2. Prefer a change to the note over a narrower reader, so the note still shows: on a turn whose
   successful calls include `list_scheduled`, word it so it says no call changed the schedule
   and asks for nothing new, in all five languages.
3. For the memory form, write near misses first (`I've updated it in memory.`, `I've updated it
   in your notes.`) and read them on a turn with a successful memory write.

## History

- 2026-11-11: filed from the first audit of the schedule claim reader's pronoun and `now goes
  off` forms ([1134](1134-a-reply-saying-it-updated-a-reminder-named-only-by-a-pronoun-gets-no-note.md)).
