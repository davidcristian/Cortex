# The result texts a model reads give an untrue reason for a row kept under an unread role

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget all 4242
apart from the card.` keeps all three rows and returns `KEPT_ALL` (`forget_unnamed.py`): each row
"is about something the user's message does not name or asks to keep". That is untrue for the
locker and the phone. `Forget the locker 4242 including the phone.` deletes the locker and returns
the text of `forgot` (`forget_results.py`): the user's message "names none of their words or asks
to keep them", which is untrue for the phone. The card line and the reply note the person reads
say only that the message was not read as meaning the rows. These three result texts are
read by the model, so a change to them can change the reply, and no draw has measured that.

## What to do

1. Write the pass rule and the rows into `docs/readings/forget-keep-except.md` before any draw:
   over the two messages above on the stack brain, count the replies that state a reason untrue
   for a kept row and the replies that claim a delete that did not happen, before and after.
2. Replace the reason in `KEPT_ALL` and in both texts of `forgot` with one that holds for every
   reason a row is kept (the user's message was not read as meaning them). The text
   must suggest no further forget call.
3. Ship the texts only if the count of false delete claims does not rise.

## History

- 2026-11-15: filed with the change that gives the card line and the reply note a reason true
  for every kept row ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
