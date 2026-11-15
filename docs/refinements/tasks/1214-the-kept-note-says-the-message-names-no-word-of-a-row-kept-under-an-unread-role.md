# The kept note says the message names no word of a row kept under an unread role

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget all 4242
apart from the card.` keeps all three rows, because no reader reads `apart from`. The result text
is `KEPT_ALL` (`forget_unnamed.py`): each row "is about something the user's message does not name
or asks to keep". That is untrue for the locker and the phone: the message asks for all rows and
asks to keep neither. The card's `KEPT_LINE` and the reply's `KEPT_NOTE` give the same reason for
the locker and the phone of `Forget the card 4242, card stays.`, which is true there, since the
message names neither. The person sees which rows were kept, but for a forget of every value the
reason shown is wrong, and nothing says that the card could not read which rows the clause after
the value asks for.

## What to do

1. Write tests first: for `Forget all 4242 apart from the card.` the result text, the card line
   and the reply note do not say the message names no word of the locker or the phone.
2. Give the rows `_may_keep` (`forget_inside.py`) keeps for an unread role their own line and
   note, true on every turn they reach: the message names a row after the value in words the
   card does not read, so every row was kept. Write each sentence in the five note languages.
3. Check the sentence against each form of the role tests in `test_forget_named_role.py`.

## History

- 2026-11-15: filed from a review of the forms the card reads after the value
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
