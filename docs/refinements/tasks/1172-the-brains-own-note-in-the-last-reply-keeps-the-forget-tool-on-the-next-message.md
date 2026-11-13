# The brain's own note in the last reply keeps the forget tool on the next message

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool when the chat's last reply
names forgetting (`_NAMES_FORGETTING`, `_ABOUT_FORGETTING`). The last reply it reads holds the notes
the brain appended to it, and `UNFORGOTTEN_CLAIM_NOTE` names forgetting in all five note languages
(`Ask again to forget it`, `Aquí no se olvidó nada`). So after a reply that claimed a forget, the
next request to remember or question keeps the tool, and an unasked call there reaches the card.
A draw of a new note of the same kind showed it: after the note on a refused setup turn, each next
message had its forget call run and its approved card delete the code row
([readings](../../readings/forget-refusal-other-languages.md)).

## What to do

1. Write tests first: `Remember that my sister is vegan.` and `Recuerda que mi color favorito es el
   verde.` after a last reply ending with `UNFORGOTTEN_CLAIM_NOTE` refuse the tool, while `Yes, do
   it.` after `Should I forget it?` and a reply whose own text names a delete keep it.
2. Leave the brain's appended notes out of the last reply before the reader reads it, by the notes'
   own texts rather than by a word list.
3. Replay every recorded message and test string with its last reply, and name every change.

## History

- 2026-11-13: filed when a note built for
  [task 1171](1171-a-request-to-remember-an-action-stated-after-que-dass-or-ca-refuses-the-forget-tool.md)
  kept the tool on the message after it in every draw.
