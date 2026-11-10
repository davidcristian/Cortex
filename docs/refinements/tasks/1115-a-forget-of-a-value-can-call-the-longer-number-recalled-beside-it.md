# A forget of a value can call the longer number recalled beside it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

With only `Remember that my phone account is 015 123 456 7890.` stored, `Forget 015 123 456 789.`
made the model call `forget_memories` with `015 123 456 7890`, a number the message does not name,
in both draws whose call texts are recorded (flow o of
[the readings](../../readings/forget-value-short-groups.md)): once as its first call, once after
`INSIDE_ALL`. The unnamed reader kept the row each time, since no word of the message names it.
Assumption, not drawn: when a word of the message names that row (`Forget my phone 015 123 456
789.` beside a row about a phone account), the card lists the longer number and the person may
approve it.

## What to do

1. Draw the assumed flow first, with a rule written before the rows: the card lists no row whose
   values do not include a value the message names.
2. If it lists one, keep a match whose whole values do not include a value of the message when
   the message names a value, the destructive card's safe side, and show it as kept.

## History

- 2026-11-10: filed from the flow o draws of the text match change.
