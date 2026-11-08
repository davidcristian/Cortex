# A forget deletes another fact that shares its number, unasked

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-08

When a `forget_memories` delete leaves other rows holding a number a deleted row held, its result
(`memory_forget_chosen.py`) ends "a forget of the number itself would remove them". On 2026-11-08
the cortex read that as a next step. Flow n1 of
[the readings](../../readings/overlay-corrections-flows.md): two chats stored `Remember that my
gym locker number is 5521.` and `Remember that the shed padlock code is also 5521.`, then a third
sent `Forget my gym locker number.` The model called `forget_memories` with `gym locker number`,
then, in the same turn and unasked, with `5521`, whose card listed the shed padlock exchange. With
the card approved, both rows were deleted and the reply said only "OK. I've forgotten your gym
locker number." So `NUMBERS_LEFT_NOTE` never showed, and the person lost a second fact without
the reply saying so. The card is what keeps the row; a person who approves without reading it
loses the fact. One draw is not a rate.

## What to do

1. Write rows and a rule into the readings, then draw n1's three turns 8 times with every card
   approved, and count turns that call a second forget with the number alone.
2. If the form repeats, change the result text so it states the rows left and tells the model to
   say so rather than to delete them, and draw again; the brain-appended note already invites the
   follow-up.

## History

- 2026-11-08: filed from flow n1 in [the readings](../../readings/overlay-corrections-flows.md).
