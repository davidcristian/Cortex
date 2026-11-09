# A forget of what was just said by its value keeps the row as unnamed

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`unnamed` (`forget_unnamed.py`) keeps every row a forget by value reaches when the person's
message names none of the row's words. A request to forget what was just said names no word of
the row, so a call passing the value reads `KEPT_ALL` and the row the chat stored one turn before
stays. In the 24 draws of [the readings](../../readings/forget-what-was-just-said.md), the x6
second turn `Actually, forget what I just told you.` passed `7319` in 6 of 8 draws and the f1 turn
`Oublie ce que je viens de te dire.` passed `5937` in 2 of 8; each of those calls kept the row.
The row stayed in 7 of 24 draws, every such reply said the fact was forgotten, and four of them had
no note, such as "I've disregarded that information." and "C'est fait, j'ai oublié cette
information." The
German x7 passed `2468` and deleted the row only because its message and the row share the word
`dir`. On 2026-11-08, before `unnamed` existed, x6 passed `7319` and deleted the row.

The safe direction of a destructive card is to keep rows, but here the kept row is the fact the
person named by "what I just told you": the chat's own last stored row.

## What to do

1. Write rows and a rule, then weigh two candidates over x6 and f1 drawn on a build of the start
   hash and on each candidate: `unnamed` never keeps the newest row the calling chat stored, or the
   keep is replaced by a brain-appended note naming what was kept, per the rule that a typed
   refusal guessing intent from a word list is replaced by a note rather than widened.

## History

- 2026-11-09: filed from the draws of
  [R-1061](1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md);
  the keep was replayed outside the stack on all three messages: `7319` and `5937` read as
  unnamed, `2468` did not.
