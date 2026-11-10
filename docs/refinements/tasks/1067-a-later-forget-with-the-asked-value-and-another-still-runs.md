# A later forget with the asked value and another still runs

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10
**Trigger:** a later `forget_memories` call, in a draw or a flow record, whose text holds the asked
value beside a phrase or another value, or names another fact by a phrase, after a delete left a
deleted number held.

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
forms of the asked value are not refused. On 2026-11-09, 24 draws of two setups made 8 later calls, each the
value alone, and neither unrefused form occurred
([the readings](../../readings/forget-shared-number.md#the-n1v-draws-2026-11-09)).

## What to do

1. When the trigger fires, write near-miss calls as tests first, then refuse a later call naming
   any value the message lacks, and read a phrase call against the rows the earlier delete left.
   A refused later call keeps rows, and a forget the person asked for is refused once at most.

## History

- 2026-11-08: filed by the audit of tonight's reader changes, from unit probes.
- 2026-11-09: drew the n1 setup 16 times and the `n1v` setup 8 times. All 8 later calls were the
  value alone, so the check is unchanged and the task waits for a form.
- 2026-11-10: checked again and not fired: in the forget draws recorded since
  (`forget-value-short-groups.md`, `forget-matched-nothing-note.md`, `forget-keep-clause.md`) no
  turn made a `forget_memories` call after an earlier call of the same turn deleted a row; the only
  turns with several calls, flow o's, deleted none.
