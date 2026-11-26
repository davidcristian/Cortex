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

The cause: `todo` and `tot` are in no cell for all, so `everything` reads no forget of everything
there, and the head after an unread first word (`_head_run`) reads nothing when a placing word
follows that word (`de`). A trial that read the English scope rule there instead (a placing word
next reads the clause as the forget's scope only when the next word past words for the or my
names the one row) kept 60 of the 94 rows asked to keep still listed over the 3,000 mixed cases,
40 of the 52 after another forget clause and 9 of the 10 placing cases, and listed none newly over
those sets. It also kept 120 rows asked to delete over the mixed cases and 20 over the placing
cases, all scope forms: `Vergiss alles von meiner Karte.`, since `meiner` is no word for the or my, and `Uită tot de
pe cardul meu.`, since `de pe` is two placing words. It was not committed (`trees/r66` in the `x2`
scratch directory of the 2026-11-26 run).

## What to do

1. Find which reader lists the row from that run, and count the same heads with the French and
   German forms over the generator.
2. Build one rule that keeps the row in every such head, replay it over every set, and draw it with
   the rows seeded.

## History

- 2026-11-26: filed from the replay of the placing word after a word for all.
- 2026-11-26: the head read after another forget clause found the same heads there, and `tot
  dulapul`.
- 2026-11-26: the English scope rule tried in the head after an unread first word; its cost is above.
