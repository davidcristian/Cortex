# A remember beside a delete request keeps the schedule tool offered

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On 2026-11-12 the `cortexn20` stack sent `Note that my gym code is now 5555, and delete the old one.`
over a stored gym code row. In one of three draws the cortex called `forget_memories` and then
`schedule_task`, which failed, although the message asks for no reminder
([readings](../../readings/forget-keep-no-call.md#a-forget-with-no-keep-clause-what-was-drawn),
proxy log lines 398 to 403). `unasked_tools` (`unasked_tools.py`) leaves the schedule tool out of
a request to remember only when every clause `actions_asked` reads asks for a reminder or a sound,
and `and delete the old one` reads as another action, so the tool stays offered.

## What to do

1. Write near misses as tests first: a request to remember beside `delete the old one`, `forget
   the old one` or `remove it` keeps no schedule tool, while `and remind me at 9` keeps it.
2. Read a clause asking to forget or delete as no action that needs the schedule tool, then
   replay the recorded remember strings through the old and new reader.

## History

- 2026-11-12: filed from the draws of the note on a forget with no keep clause and no call.
