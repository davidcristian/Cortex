# A forget call refused for words a request to remember lacks gets no held note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-27

`REFUSED_HELD_NOTE` (`forget_refused_held.py`) closes a reply when a stored row holds whole a
value that a refused `forget_memories` call named. `run_round` (`dispatch_round.py`) keeps the
text of a call only when its refusal is in `_UNASKED`: `UNASKED` or `FORGET_UNREQUESTED`. A call
that `FORGET_UNSAID` refuses (`forget_unsaid.py`: the person asked to remember something and the
call names words the message does not hold) keeps no text, so its turn gets no note.

## The draws

On 2026-11-27, with `Retiens que mon code est 5528.` stored first, `Retiens que ce numéro est
faux.` drew a forget call with the text `5528` in 4 of 8 draws, each refused by `FORGET_UNSAID`.
No reply had a note, each said the number was noted as wrong, and the row still held `5528`
([readings](../../readings/note-language-letter-tie.md#the-live-draw-2026-11-27)). The same call
on `Retiens que ce code est périmé.` was refused by `FORGET_UNREQUESTED` and got the French note
in 2 of 2 draws. What the person ends up with is the safe side for the forget tool (the row is
kept), but they are not told that it still holds the value.

## What to do

1. Add `FORGET_UNSAID` to the refusals whose call texts `run_round` keeps in
   `TaintLedger.forget_refused_texts`. The note's text says only that the call was not run and a
   remembered exchange still holds what it named, which is true after this refusal too. No forget
   reader changes, so the freeze of the forget message readers does not apply.
2. Write the rule and rows before the draw: the q2 label of the draw above, 8 draws with the old
   row seeded, passing when every draw with a refused call naming `5528` shows the French note
   and the seeded row is kept in every draw.

## History

- 2026-11-27: filed from the live draw of the note language tie.
