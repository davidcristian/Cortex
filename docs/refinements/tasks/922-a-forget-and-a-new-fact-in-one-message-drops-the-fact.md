# A forget and a new fact in one message drops the fact

**Status:** done 2026-10-29
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

A turn that calls `forget_memories` is never recorded to memory, because its query or reply may
name the text it forgets. So a message that also states a new fact loses it: "Forget my card number
4242 4242 4242 4242, and remember that my locker code is 7319." removed the card row, stored no
row holding `7319`, and replied "I've forgotten your card number and noted that your locker code
is 7319." The person is told a fact was kept that no later chat can recall
([readings](../../readings/forget-chosen-memories.md#a-forget-and-a-new-fact-in-one-message-2026-10-28)).

Recording the turn is not the remedy: the value can appear in the query in another form than the
argument the model passed (a keyword such as `passport`), so masking the argument is not enough.

## What to do

1. Write rows and a pass rule in the readings first: the message above and two variants, five
   draws each; a draw passes when the reply does not say the new fact was kept and asks the person
   to say it again in its own message.
2. Then change the forget's result texts (`memory_forget_chosen.py`) to say that this message is
   not remembered, so anything else in it must be said again, and ship it only if the rule passes.

## History

- 2026-10-28: filed from the second audit of the forget tool, with one draw on the `cortexn9` stack.
- 2026-10-29: done. Every result a `forget_memories` call gets, whether it ran or was declined,
  expired or refused, now ends with `FORGET_NOT_KEPT_NOTE`: nothing in the message is kept, the
  reply must not say it was noted, and the person is asked to send anything else again. A first
  wording failed the rule on N2 and the second passed it, 13 of 15 N draws against 0 of 15 with no
  note; with the card declined, 5 of 5 against 0 of 5. Filed task 926, a request to remember that
  calls the forget.
