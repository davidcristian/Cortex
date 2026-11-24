# A first item before a comma in a list adding rows is a remark

**Status:** done 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242` and a row `Remember that my
gym code is 4242.`, the message `Forget the card 4242, the phone, the locker and the gym too.`
deletes the card, the locker and the gym code and keeps the phone. `asking` (`forget_clauses.py`)
reads each clause between commas alone: `the locker and the gym too` adds rows, and `the phone`
holds no adding word, so it is a remark. This keeps a row, the safe direction, and the card shows
it as kept.

## What to do

1. Write tests first: the message above deletes all four rows; `Forget the card 4242, my phone,
   keep the locker and the gym too.` and `Forget the card 4242, the phone, I think, the gym too.`
   keep the phone.
2. Read a clause that is one item (`_item` in `forget_clauses.py`) as adding rows when the next
   clause is one too or only adds rows (`_adds`), reading the clauses from the last one back, in
   `asking`. That file has 298 lines, so first move `asking` and its helpers to a module of their
   own.
3. Replay every string literal of the brain's forget tests through the card before and after, and
   count rows newly deleted: each must be one the message asks to delete.

## History

- 2026-11-15: filed while closing
  [task 1201](1201-a-clause-adding-two-rows-to-a-forget-is-a-remark.md).
- 2026-11-24: done. The premise held. `asking` and its helpers moved to `forget_remarks.py`,
  where `_listing` reads the clauses from the last one back and reads a clause that is one `_item`
  as adding rows when the next clause only adds rows. The first message deletes all four rows, and
  the other two keep the phone. Over the forget card generator with this task's forms added, the
  rows asked to delete that the card keeps fell by 29, all English, French and German, no row
  asked to keep is listed, and no other row of the generator, of the string literals of the
  brain's forget tests or of the word pairs of the 2026-11-23 audit changed
  ([readings](../../readings/forget-added-list.md#a-first-item-before-a-comma-2026-11-24)).
