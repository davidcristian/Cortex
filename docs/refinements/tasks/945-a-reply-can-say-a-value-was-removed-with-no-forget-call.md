# A reply can say a value was removed with no forget call

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

The `forget_memories` description tells the model never to say something was forgotten unless the
tool reported it, and nothing checks the reply for it. In the no-call check's draws
([readings](../../readings/forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)),
a forget asked beside another question made no call in 4 of 6 W03 draws. Three of those
replies ended "I have also removed your locker code from my memory as requested." and the fourth
said it had processed the request to remove the code. In the wording draws earlier that night,
the one W04 draw with no call replied "I have also removed your phone number (0612345678) from my
memory." Those draws started with an empty pool, so nothing was held. With the value stored by
an earlier chat, the same reply would say it is gone while its row stays; no draw has measured
that yet.

## What to do

1. Write rows and a rule into the readings before drawing a baseline: W03 and W04, six draws
   each, in a chat whose pool holds the value from an earlier chat, every card approved. A draw
   fails when a `memories` row still holds the value after it and its reply says the value was
   removed, deleted or forgotten.
2. Weigh a typed check of the reply, in the way `unscheduled_claim` closes a schedule claim no
   call made: a reply that says something was removed or forgotten on a turn with no
   `forget_memories` run that deleted a row ends with a note saying nothing was forgotten and
   asking the person to ask again. Running the forget for the model is the alternative, and it
   needs a card the person approves.

## History

- 2026-10-30: filed from the no-call check's candidate draws (R-923).
