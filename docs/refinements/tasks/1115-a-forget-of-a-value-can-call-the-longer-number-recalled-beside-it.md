# A forget of a value can call the longer number recalled beside it

**Status:** done 2026-11-11
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

With only `Remember that my phone account is 015 123 456 7890.` stored, `Forget 015 123 456 789.`
made the model call `forget_memories` with `015 123 456 7890`, a number the message does not name,
in both draws whose call texts are recorded (flow o of
[the readings](../../readings/forget-value-short-groups.md)): once as its first call, once after
`INSIDE_ALL`. The unnamed reader kept the row each time, since no word of the message names it.

When a word of the message names the row, the card lists the longer number. Unit calls on
2026-11-10, the call text `015 123 456 7890` and that row alone: `Forget 015 123 456 789.` keeps
it (`KEPT_ALL`), while `Forget my phone 015 123 456 789.`, `Forget my phone account 015 123 456
789.` and `Forget the phone number 015 123 456 789.` each show a card listing it to delete. The
refusal of a call naming a value the message lacks (`value_unasked` in `forget_value_unasked.py`)
does not reach this form: it applies only after a delete of the turn left rows holding a deleted
number, and here nothing was deleted.

A rule comparing values alone cannot separate this form from flow e, where `Forget the card ending
in 4242.` called `4242 4242 4242 4242` and the card rightly deleted the card row: in both, the
call's value (`whole_values` and `digit_runs`) is one the message lacks and holds the message's
value. What separates them is where the message's value sits in the row: `4242` is a whole group of
the card number, while `015 123 456 789` ends inside the group `7890`, which is the test `inside`
(`forget_inside.py`) already makes for a call's text.

## What to do

1. Draw the form first (`Forget my phone 015 123 456 789.` beside the account row alone), with a
   rule written before the rows: the card lists no row in which every value the message names
   occurs only inside a longer value.
2. If it lists one, keep a match when the call's value is not among the message's values and
   `inside` keeps the match for every value form the message names, show it under `INSIDE_LINE`,
   and check flow e and flow b still delete their rows.

## History

- 2026-11-10: filed from the flow o draws of the text match change.
- 2026-11-10: the assumed listing confirmed at unit level, the refusal found not to reach it, and
  the remedy rewritten so a card by its end (flow e) still deletes.
- 2026-11-11: done without a draw of the form, as step 2: `longer` in `forget_longer.py` keeps the
  match and the card shows it under `LONGER_LINE`; flows e, w and a forget of what was just said
  still delete their rows ([readings](../../readings/forget-value-short-groups.md)). A row kept
  this way with no card is named after the reply by `longer_note`.
