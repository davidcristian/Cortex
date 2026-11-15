# A forget of every value but one row is refused with an untrue account of the tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

On 2026-11-15 the `cortexn23` stack brain, built from the tree that reads the role of a row named
after the value, stored a locker code, a card and a phone sharing `4242`, each in its own chat
over an emptied memory, and was then sent `Forget all 4242 apart from the card.` in a new chat. In
2 of 2 draws the cortex made no forget call and the reply said the tool cannot do it, as in "My
forget tool deletes every memory that includes the specified text, so removing all instances of
4242 would also delete the memory of your card." That is untrue: the card lists rows for approval
and keeps a row the message asks to keep. `Forget all 4242 except the card.` made no call in 2 of
2 draws either, and each reply said the card is the only memory holding `4242`
([task 1151](1151-recall-leaves-out-the-rows-a-forget-of-everything-but-one-fact-asks-to-delete.md)).
`UNCALLED_FORGET_NOTE` closed all four replies and is true on each. `Forget all 4242, only the
card.` called the tool in 2 of 2 draws, the card listed the card row and showed the other two
as kept, and it was approved; one reply then said it cannot forget part of a memory and asked
whether to keep the card number, which the call had deleted. Engine build
`b12375-9d25e0014`. The driver output is `live1.log` to `live6.log` in
`/home/david/.cache/cortex-run/2026-11-15/slot6/`.

## What to do

1. Write the rows and the pass rule in `docs/readings/forget-keep-no-call.md` before any draw:
   over the three rows, count the draws of each message that make a forget call, and the replies
   that say the tool cannot keep a row.
2. Read the first request of a drawn turn in the recording proxy's log: the rows recall put in it
   and what the tool's description says about a row the message asks to keep.
3. Prefer a typed result text or a note the brain appends after a typed check of the reply over a
   prompt rule.

## History

- 2026-11-15: filed from six draws on the live stack after the changes to the rows the card lists.
