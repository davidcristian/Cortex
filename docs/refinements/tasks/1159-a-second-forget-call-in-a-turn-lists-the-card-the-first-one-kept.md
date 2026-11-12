# A second forget call in a turn lists the card the first one kept

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

The last group keep beside a whole value keeps a card ending in a code while another row holds the
code whole, but its card step reads only the rows still stored. Over `User: Remember that my card
is 4111 1111 1111 4242.` and `User: Remember that my gym code is 4242.`, with the message `Forget
my gym code 4242.`, a first `forget_memories` call with text `4242` lists the gym row and keeps
the card. A second call in the same turn with text `4242` then lists the card, and an approval
deletes it; the same happens when the first call's text is `gym code`
([readings](../../readings/forget-keep-plain-replay.md#two-calls-and-every-row)). In `_choose`
(`memory_forget_chosen.py`) `inside` gets no `held` texts, while `invoke` passes the texts it just
deleted, so the rows a call of the same turn deleted earlier are not read on the card.

## What to do

1. Write the two-call case as a test first, with a near miss: a second call after a message naming
   the card (`Forget my gym code and the card ending in 4242.`) still lists the card.
2. Pass the turn's deleted row texts (`_deleted_rows`) to `inside` in `_choose`, then replay the
   strings of the readings through the old and new code.

## History

- 2026-11-12: filed from the replay of plain forgets through the destructive card.
