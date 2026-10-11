# A reply says it set a reminder it only found listed

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-11

Asked "Remind me tomorrow at 10:00 to check whether the bulb order went out." in a fresh chat,
after earlier chats had stored the same reminder, the cortex sometimes calls only
`list_scheduled`, finds that reminder among the items it lists, and replies "OK. I've set a
reminder for you tomorrow, October 12th, at 10:00 AM ...". No `schedule_task` call is made and
nothing is stored, yet the reply is word for word the one a stored reminder gets. This happened
in 1 of 10 chats with that request and 1 of 5 with "Can you remind me at 10:00 tomorrow to check
on the bulb order?", with 12 and 15 such reminders already stored
([readings](../../readings/recalled-tool-runs.md#results)).

The person is reminded, by an item another chat stored, so the reminder itself is not lost. The
reply is false about what this turn did.

## What to do

Decide what the cortex should say, and what result text leads it there, when the reminder asked
for already exists: for example, `schedule_task` could find an active item with the same text and
due time and return a typed result naming it instead of adding a duplicate, so the turn makes the
call and has a result to report; or `list_scheduled`'s result could say that listing changes
nothing. Write the rows and the pass rule into the readings before the baseline: the shape above,
fifteen fresh chats over a store holding the same reminder, counting turns whose reply says a
reminder was set with no `schedule_task` call.

## History

- 2026-10-11: filed from the recall rows of
  [R-836](836-a-recalled-exchange-is-claimed-again-with-no-call.md).
