# A listing's next-day item is read as tomorrow

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-12

Asked "Set a reminder for tomorrow at 9:00 to call Ana about the bulb payments." on a full
schedule whose 28 "call Ana" items were due daily from the day after tomorrow, the cortex called
only `list_scheduled` in two of five chats and replied that the reminder was already set for
tomorrow; one reply named the later date as "tomorrow, October 14th" and said the existing item
"covers this request". Nothing was stored, and no item was due tomorrow
([readings](../../readings/schedule-full-cancel.md#a-cancel-card-shown-on-a-tainted-turn), row
G2). The listing writes each due time as an ISO-8601 instant and states no current date; only
`schedule_task`'s description does.

## What to do

Row G2 with ten repeats and every memory row the run wrote deleted before each chat was null: no
chat listed before calling `schedule_task`, and none misdated an item
([readings](../../readings/schedule-full-cancel.md#a-next-day-item-read-as-tomorrow)). In the
first run every chat that listed first had recalled one earlier G2 exchange. The next row is G2
with that memory kept: before each chat, the schedule is reseeded and memory holds the earlier
slots' seed plus one untainted G2 exchange whose `schedule_task` call failed as full; ten repeats,
counted and judged by the rule already in the readings, written as a new row before its baseline.

The change to test (built and unit-tested, not shipped): `ListScheduledTool` takes a `Clock`, the
listing opens with the sentence `schedule_task`'s description uses ("The current date-time is
..."), and each due time names its calendar day counted from today in the item's own zone
("today", "tomorrow", "in 2 days", "yesterday"). The cancel card keeps the plain line.

## History

- 2026-10-12: filed from row G2, run for
  [R-837](837-a-cancel-of-a-scheduled-item-needs-no-confirmation.md).
- 2026-10-12: G2 with memory reset before each chat was null, 0 of 10; the next row keeps one
  earlier G2 exchange in memory.
