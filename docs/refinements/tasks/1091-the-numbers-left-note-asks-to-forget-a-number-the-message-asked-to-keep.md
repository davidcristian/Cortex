# The numbers left note asks to forget a number the message asked to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_holding` in `memory_forget_chosen.py` counts every remaining row holding a deleted number,
including a row a keep clause kept. After `Forget my bike lock code 7319, keep the shed one.` is
approved and the reply names the removal, `NUMBERS_LEFT_NOTE` ends the reply with `Ask to forget
the number itself to remove it.`, a destructive step on the row the person asked to keep. The
rows such a card kept are also never named in a closing note, since `KeptRows` records only a
call whose rows were all kept ([readings](../../readings/forget-count-note.md#second-audit-probes-2026-11-09)).

## What to do

1. Write the turn above as a test first, with a near miss whose kept row the message did not ask
   to keep (an unnamed row), where the note must still show.
2. Leave the rows a keep clause named out of `_holding`, which needs `unnamed` to return them
   apart from the unnamed rows.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
