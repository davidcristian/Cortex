# A forget naming no row lists the card the chat just stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

In the chat that stored only `Remember that my card is 4111 1111 1111 4242.`, `Forget my gym
code.` with the call text `4242` lists and deletes the card. `inside` (`forget_inside.py`) keeps a
last group the message names no word of, but never the newest row the calling chat stored when the
message names no word of any match, since `Forget what I just told you.` must still delete that
row. Both messages name only words no row holds (`gym`, `told`), so the reader cannot tell them
apart ([readings](../../readings/forget-last-group-beside-whole.md)).

## What to do

1. Write the rows as unit tests first: the card stored in the calling chat, the text `4242`, and
   `Forget my gym code.` (keeps the card), `Forget what I just told you.`, `Forget that.` and
   `Vergiss, was ich gerade gesagt habe.` (each lists it).
2. Find a reading that separates a message naming another fact from one pointing back at the last
   thing said, without a word list of verbs of saying, then replay the recorded forget strings
   through the old and new code.

## History

- 2026-11-12: filed from the unit rows of the last group keep with no row holding the code whole.
