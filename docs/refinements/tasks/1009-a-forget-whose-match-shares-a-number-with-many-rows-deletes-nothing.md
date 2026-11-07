# A forget whose match shares a number with many rows deletes nothing

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`ForgetChosenTool._choose` refuses the whole forget when the rows the text matches plus the rows
that repeat one of their values are more than `FORGET_CHOSEN_LIMIT` (20). The refusal says `more
than 20 remembered exchanges contain that text, so ask the user for a longer, more exact text`,
which is false when the text matched one row: the extra rows come from a shared value, and a
longer text does not remove them.

Unit reproduction: one row `User: Remember that my phone number is 0176 5550 1234.` and twenty
rows `User: Remember that friend N's number is 0176 ... 0000.`, then a forget of `my phone
number`. The card is `None`, the result is the refusal above, and all 21 rows stay. Before the
card listed repeats, the same call listed and deleted the one row. A year such as `2026` in many
rows that also hold a common word of the text does the same.

## What to do

1. Write the reproduction as a failing test. The current test
   `test_repeats_past_the_limit_delete_nothing` asserts the refusal for repeats of the asked value;
   decide on both cases together.
2. When the text matches at most the limit and only the repeats pass it, either list the text
   matches alone and say in the result that rows holding the value were left, or refuse with a
   result that names the cause (rows that hold a number of the match) rather than the text.
3. Task 1008 narrows what counts as a repeat, which makes this case rarer but does not remove it.

## History

- 2026-11-07: filed by the audit of the card that lists rows repeating a value.
