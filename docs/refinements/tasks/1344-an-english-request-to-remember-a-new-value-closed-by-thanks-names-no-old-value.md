# An English request to remember a new value closed by thanks names no old value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

The old value note (`memory_old_value.py`) reads an English statement only when no later
sentence follows it, and `THANKS` (`memory_request.py`) holds the thanks words of French, German,
Spanish and Romanian only. So beside a stored `Remember that my code is 90909.`,
`Remember that my code is 5528. Thanks!`, `Remember that my code is 5528, thanks.` and `My code
is 5528. Thanks!` show no note, while `Retiens que mon code est 5528. Merci !` and the German,
Spanish and Romanian forms with thanks name `90909`. The tree before the night behaves the same
for English. A missing note leaves both values stored with nothing said, the unsafe direction of
a reply note ([readings](../../readings/old-value-other-languages.md)).

## What to do

1. Add English thanks forms (closing sentence, closing comma clause, opening sentence) to the old
   value corpus of `~/.cache/cortex-run/2026-11-25/s2/replay/` and count notes.
2. Fill the English cell of the thanks words, with no other change. `THANKS` is shared with
   `asks_kept_alone` and `fact_asked_other`, so replay the forget refusal readers and the forget
   generator too: no message may newly keep or lose the forget tool, and no note may name a value
   of another fact.

## History

- 2026-11-25: filed by the audit of the night's forget commits.
