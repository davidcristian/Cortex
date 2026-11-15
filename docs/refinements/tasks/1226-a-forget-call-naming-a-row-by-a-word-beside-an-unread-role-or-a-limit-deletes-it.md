# A forget call naming a row by a word beside an unread role or a limit deletes it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

A row named after the call's value has a limit, an addition or an exception as its role, and the
card keeps every row when no reader reads the role. That holds only for a call text holding the
value. On 2026-11-15 unit calls through `ForgetChosenTool` over a locker code, a card and a phone
that all end in `4242` deleted a row the message does not ask to delete, at the published build
and at the tree alike:

| Message | Call text | Deleted |
| --- | --- | --- |
| `Forget all 4242 apart from the card.` | `card` | the card, which the message asks to keep |
| `Forget all 4242, card stays.` | `card` | the card, which the message asks to keep |
| `Forget all 4242, only the card.` | `locker code` or `phone` | that row, which the message does not ask for |
| `Forget all 4242 but only the card.` | `locker code` or `phone` | that row, under a role no reader reads |

With the call text `4242` the first, second and fourth message keep all three rows and the third
deletes only the card. In two model draws of the first message the calls named `locker code` and
`phone`, never `card`. The card shows each row before anything is deleted.

## What to do

1. Write the near misses as tests first: `Forget all 4242 except the card.` and `Forget everything
   but my card.` with the call text `locker code` must still delete the locker code.
2. Apply the roles `beside` reads (`forget_clauses.py`) and `after_value` to a match of a call text
   holding no digit as `_may_keep` applies them to a match of the value, so a row is listed only
   when every role not ruled out lists it.
3. Replay the three pools of the reading with each row's own word as the call text: no row newly
   listed, and count the rows newly kept that the message asks to delete.

## History

- 2026-11-15: filed from the unit calls run beside the redraw of the committed build
  ([readings](../../readings/forget-everything-but-call.md#the-committed-build-redrawn-2026-11-15)).
