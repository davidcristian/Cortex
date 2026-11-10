# A correction naming an old value is stored when no forget deleted it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-10

`asks_not_kept` (`memory_request.py`) reads none of these messages as asking to drop the old
value, while `asks_kept` reads each as a request to remember (unit calls, 2026-11-10):

- `My phone is no longer 015 123 456 789, it is 0170 5555. Remember it.`
- `Replace 015 123 456 789 with 0170 5555 and remember it.`
- `Change my phone from 015 123 456 789 to 0170 5555, remember that.`
- `My new phone is 0170 5555, not 015 123 456 789. Remember it.`
- `Update my phone: 0170 5555 instead of 015 123 456 789. Please remember.`
- `Remember 0170 5555 as my phone instead of 015 123 456 789.`
- `015 123 456 789 is wrong, my phone is 0170 5555, remember it.`

So `memory_withheld` stores such a turn when it called no forget, or when every forget call
matched nothing (`_unmatched_keep`), and the stored exchange holds the old value the person asked
to replace. When a call deletes a row or returns `INSIDE_ALL`, the turn is withheld. Treating
`INSIDE_ALL` like a call that matched nothing was weighed on 2026-11-10 and declined for this
reason: the call's text in these forms is the old value, so the change would store it.

## What to do

1. Decide whether storing the old value of a correction is a privacy loss. The do-not-keep
   reader's safe side is to withhold, and `UNKEPT_CLAIM_NOTE` tells the person.
2. If it is, write near-miss tests first (a correction with no old value, `not` in another
   clause, a question), replay every recorded draw message in `docs/readings/` through the old and
   new reader, then read these forms as asking not to keep the old value.

## History

- 2026-11-10: filed from the unit check of a remember turn whose forget kept only longer values.
