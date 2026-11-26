# A Spanish or Romanian head before a kept row lists that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Olvida todo de eso la tarjeta se queda.` and `Uită tot de pe el cardul rămâne.` list the row they
ask to keep, for the call text `4242` and for the row word: 10 of the 144 forgets of everything
with a placing word after the word for all (`placegen.py` in `~/.cache/cortex-run/2026-11-26/f5/`)
list a row asked to keep, at the tree before the night's head rules and after them
([readings](../../readings/forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).
`_head_run` (`forget_permit.py`) reads the words after `todo` and `tot` as one more run, and that
run still names the row in a role a reader reads.
`Uită tot dulapul rămâne.` lists the locker for the call text `dulap`, and each of these heads lists
its row after another forget clause as well (`Olvida el teléfono. Olvida todo de eso la tarjeta se
queda.`): 96 rows over the two generators of the head after another forget clause
([readings](../../readings/forget-form-cells.md#a-head-after-another-forget-clause-2026-11-26)).

## What to do

1. Find which reader lists the row from that run, and count the same heads with the French and
   German forms over the generator.
2. Build one rule that keeps the row in every such head, replay it over every set, and draw it with
   the rows seeded.

## History

- 2026-11-26: filed from the replay of the placing word after a word for all.
- 2026-11-26: the head read after another forget clause found the same heads there, and `tot
  dulapul`.
