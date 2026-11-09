# The kept rows note is English beside notes in the message language

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-09

`kept_note` in `forget_unnamed.py` writes `KEPT_NOTE` in English only, while the count note and
the numbers left note beside it take the message's language. A French forget that kept a row ends
with a French count note, a French numbers left note and an English kept rows note ([readings](../../readings/forget-count-note.md#second-audit-probes-2026-11-09)).

## What to do

Propose `KEPT_NOTE` in French, German, Spanish and Romanian in this file for review, since a
wording in another language is a pick, then pass the message language to `kept_note` as the other
notes do. Proposed: `(Toujours en mémoire, car votre message n'en nomme aucun mot ou demande de les
garder :`, `(Noch gespeichert, weil Ihre Nachricht keines ihrer Wörter nennt oder darum bittet, sie
zu behalten:`, `(Todavía en memoria, porque tu mensaje no nombra ninguna de sus palabras o pide
guardarlos:`, `(Încă în memorie, pentru că mesajul tău nu numește niciun cuvânt al lor sau cere să
fie păstrate:`.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
