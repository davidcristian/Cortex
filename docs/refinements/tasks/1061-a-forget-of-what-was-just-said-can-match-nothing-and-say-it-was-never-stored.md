# A forget of what was just said can match nothing and say it was never stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

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

1. Draw x7 again under [the rule](../../readings/forget-what-was-just-said.md#rows-and-the-rule-2026-11-09)
   on a build of [the recorded patch](../../readings/forget-value-held-patch.md), after R-1074
   changes how the same rows end, with a Spanish form beside it.

## History

- 2026-11-08: filed from flow x7 in [the readings](../../readings/overlay-corrections-flows.md).
- 2026-11-09: the premise holds in the code. The candidate is a note the brain appends when an
  unmatched call's text names a whole value a row still holds; it reads no reply, so the German
  reply needs no reader, and the result text the model reads is unchanged. Its rows and rule were
  written first, and 24 draws of x6, x7 and a French form on the base and the candidate gave the
  form in none, so the rule gave no result and the candidate is
  [recorded as a patch](../../readings/forget-value-held-patch.md). The draws found the keep filed
  as [R-1074](1074-a-forget-of-what-was-just-said-by-its-value-keeps-the-row-as-unnamed.md) in 8 of
  24, and a lost French request to remember, filed as
  [R-1075](1075-a-french-request-to-remember-that-raises-a-forget-call-keeps-nothing.md).
