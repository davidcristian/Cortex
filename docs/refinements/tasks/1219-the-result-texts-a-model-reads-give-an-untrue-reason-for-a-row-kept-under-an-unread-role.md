# The result texts a model reads give an untrue reason for a row kept under an unread role

**Status:** done 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, `Forget all 4242
apart from the card.` keeps all three rows and returns `KEPT_ALL` (`forget_unnamed.py`): each row
"is about something the user's message does not name or asks to keep". That is untrue for the
locker and the phone. `Forget the locker 4242 including the phone.` deletes the locker and returns
the text of `forgot` (`forget_results.py`): the user's message "names none of their words or asks
to keep them", which is untrue for the phone. The card line and the reply note the person reads
say only that the message was not read as meaning the rows. These three result texts are
read by the model, so a change to them can change the reply, and no draw has measured that.

The candidate texts, the rows and the rule written before the draws are in the
[readings](../../readings/forget-result-texts.md#the-reason-given-for-rows-kept-under-an-unread-role-2026-11-24).

## History

- 2026-11-15: filed with the change that gives the card line and the reply note a reason true
  for every kept row ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-24: drawn on the stack brain under the rule, every card approved, 8 draws per message
  and build: false delete claims 12 of 16 on the base and 12 of 16 on the candidate, untrue
  reasons 1 and 0. Equal counts pass the rule, so `KEPT_ALL` and the two kept texts of `forgot`
  now say that the message was not read as meaning the rows. The false delete claims are
  [R-1320](1320-a-reply-says-a-row-the-forget-kept-was-forgotten.md).
