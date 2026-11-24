# The result texts a model reads give an untrue reason for a row kept under an unread role

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

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

1. Draw the rows below on the stack brain under the rule, base and candidate on one night. The
   rule is written here because `docs/readings/forget-keep-except.md` is at the line limit; the
   draws go into a readings record of their own, with the rule moved there.
2. Ship the candidate texts only when the rule passes. Each states one reason that holds for
   every reason a row is kept, and none suggests a further forget call:
   - `KEPT_ALL`: `nothing was forgotten: the user's message was not read as meaning any
     remembered exchange holding that value, so each was kept`
   - `forgot`, a text holding no digit: `forgot {removed} remembered exchanges; {kept} other
     remembered exchanges contain that text, and the user's message was not read as meaning
     them, so they were kept`
   - `forgot`, a value: `forgot {removed} remembered exchanges; {kept} other remembered
     exchanges hold the same value, and the user's message was not read as meaning them, so they
     were kept and the value is still remembered`

**Rows and rule, written 2026-11-24 before any draw.** The stack brain on compose defaults, the
three rows above put back under new ids before each draw, one turn in a new chat per draw, every
card approved. Base is the tree as it stands; the candidate is the same tree with the three texts
above. Each of the two messages above is drawn 8 times per build. After each turn the store is
read, and each reply is counted for a **false delete claim** (it says a row was forgotten that the
store still holds) and an **untrue reason** (it says the message did not name a kept row, or that
the person asked to keep it, for the locker or phone of the first message or the phone of the
second). The candidate ships when its false delete claims over its 16 draws are no more than the
base's; equal counts ship it. The untrue reasons are reported and do not decide. No rate is
drawn, so the power limit does not matter.

## History

- 2026-11-15: filed with the change that gives the card line and the reply note a reason true
  for every kept row ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-24: checked on the tree as it stands, with the forget tool over the three rows and the
  call text `4242`: the first message keeps all three rows and returns `KEPT_ALL`, the second
  deletes the locker and returns the value text of `forgot`, each with the reason above. The rule
  and the candidate texts are written above; no draw was made, since this was a slot with no card
  work.
