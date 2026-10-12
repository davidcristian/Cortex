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

Measure first: row G2 with ten repeats, counting replies that say a reminder exists for a day on
which no listed item is due. Candidate result-text changes, each a hypothesis: open the listing
with the current date-time, as `schedule_task`'s description does, or add a relative day ("today",
"tomorrow", "in 2 days") to each due time. Write the pass rule into the readings before the
baseline.

## History

- 2026-10-12: filed from row G2, run for
  [R-837](837-a-cancel-of-a-scheduled-item-needs-no-confirmation.md).
