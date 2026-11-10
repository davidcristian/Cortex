# A forget whose only match holds a longer value names the kept row only to the model

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

When every text match of a `forget_memories` call holds its text only inside a longer value
(`inside` in `forget_inside.py`), the call shows no card and returns `INSIDE_ALL`, which the model
reads. No note the brain appends names the kept row, so the person learns that it stayed only if
the reply says so. A card with other rows lists such a row under `INSIDE_LINE`, so the person sees
it there. `kept_note` cannot name it, since its header gives another reason ("your message names
none of their words or asks to keep them").

## What to do

1. Add a result field and a `TaintLedger` field for these excerpts, passed through the handoff
   record like `forget_kept`, and a note the brain appends naming them: the rows still in memory,
   since each holds that text only inside a longer value.
2. The note in French, German, Spanish and Romanian is a wording pick: propose it here first.
3. Draw flow o of [the readings](../../readings/forget-value-short-groups.md) before and after.

## History

- 2026-11-10: filed when the card started keeping a text match inside a longer value; the card
  case shows the row, the case with no card does not.
- 2026-11-10: in the four flow o draws of [the readings](../../readings/forget-value-short-groups.md)
  each reply showed the row only through `kept_note`, which only a `KEPT_ALL` call sets: in the
  two recorded draws, a call of the longer number (task 1115).
