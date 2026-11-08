# A forget of what was just said can match nothing and say it was never stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

Flow x7 of [the readings](../../readings/overlay-corrections-flows.md), one chat, every card
approved: `Mein Fahrradschloss hat den Code 2468, merk dir das.` was stored as an exchange row, and
the reply said the code was noted. The next turn, `Vergiss bitte, was ich dir gerade gesagt
habe.`, called `forget_memories` once; its thinking planned the text `Fahrradschloss Code 2468`,
which no row contains, since the row reads `Fahrradschloss hat den Code 2468`. The result was
`_NONE_FOUND` (`memory_forget_chosen.py`), which tells the model to say nothing about it was
stored, and the reply said "Ich habe festgestellt, dass ich mir diese Information ohnehin nicht
dauerhaft gespeichert hatte, daher ist nichts gelöscht worden." The row stayed and no note was
appended: `DELETED_UNFOUND_NOTE` needs a call of the turn that deleted rows, and `says_not_stored`
reads English. The English flow x6 (`Actually, forget what I just told you.`) passed `7319` and
deleted the row.

This is the form of R-969 where the person names no value at all, so the model must build the text
from the previous turn. One draw is not a rate.

## What to do

1. Write rows and a rule into the readings, then draw x6 and x7 and a French and a Spanish form 6
   times each, counting forget calls that match nothing while the previous turn's row holds the
   fact.
2. Weigh a result for an unmatched call that names the rows the chat's last turn stored, against
   the R-969 patch, before any new wording.

## History

- 2026-11-08: filed from flow x7 in [the readings](../../readings/overlay-corrections-flows.md).
