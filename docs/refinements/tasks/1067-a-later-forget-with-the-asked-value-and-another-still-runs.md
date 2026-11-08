# A later forget with the asked value and another still runs

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

`value_unasked` in `forget_value_unasked.py` refuses a later `forget_memories` call, after a delete
left a deleted number held, only when the call's values and the message's values share none. Unit
probes on 2026-11-08 with `Forget my door code 5521.` as the message:

| Call text | Refused once |
| --- | --- |
| `the locker code is 4412 and door 5521` | no |
| `my locker code` | no (no value) |
| `5521 4412` | yes |
| `four four one two` | no (no value) |

So a call holding the asked value beside another, or naming the other fact by a phrase, runs with
its card. Forgets the person asked for that the refusal stops once (the safe side): `Forget that
number.` with the call `5521` is refused once. `55 21` against `5521` and the French and German
forms of the asked value are not refused. How often the model sends the two unrefused forms has
not been drawn.

## What to do

1. Draw the setup in [the readings](../../readings/forget-shared-number.md) on the stack and count
   the later calls by form before changing the check.
2. If a form occurs, refuse a later call naming any value the message lacks, and read a phrase
   call against the rows the earlier delete left.

## History

- 2026-11-08: filed by the audit of tonight's reader changes, from unit probes.
