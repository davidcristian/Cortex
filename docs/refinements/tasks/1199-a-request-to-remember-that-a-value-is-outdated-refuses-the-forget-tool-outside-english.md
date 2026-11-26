# A request to remember that a value is outdated refuses the forget tool outside English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`forget_unrequested` keeps the forget tool when a word of `RETRACT_WORDS` can retract a stored
fact. English reads `outdated`, `obsolete`, `stale` and `wrong`, so `Remember that the number is
outdated.` keeps it. The French, German, Spanish and Romanian words for the same thing are not in
the list, and `asks_kept_fact_other` reads each message below as a stated fact, so each is refused
on the start build of 2026-11-14 and on HEAD (`forget_unrequested` alone, no model):
`Merk dir, dass die Nummer veraltet ist.`, `Merk dir, dass der Code ungültig ist.`, `Merk dir,
dass der Termin abgesagt ist.`, `Retiens que ce code est périmé.`, `Retiens que mon adresse est
fausse.`, `Recuerda que ese número ya es viejo.`, `Recuerda que el código está caducado.`, `Ține
minte că numărul acela e expirat.` and `Ține minte că parola e invalidă.`.

A new value has the same shape: `Souviens-toi que mon vélo est bleu.`, `Recuerda que soy
vegetariano.`. A rule that keeps the tool on a value of one lowercase word keeps it on both, and
with the old value stored an unasked forget call then deleted the old row
([readings](../../readings/forget-refusal-stated-fact.md#a-new-value-with-the-old-one-already-stored)).

## What to do

1. The cost side is drawn: with the old value stored, the German and Spanish messages each had a
   refused call in 3 of 8 draws and no note, so the person kept the old code without being told
   ([readings](../../readings/forget-refusal-stated-fact.md#a-value-said-to-be-outdated-the-old-value-stored-2026-11-26)).
2. That cost is real. Count, over the 7 draws with a refused call, whether a note shown when a
   refused forget call names a value a stored row holds would reach each of them: it keeps the
   refusal and tells the person. Write the note to be true on every turn it reaches, with its
   tests first. `forget_unrequested` is not widened and no word list of words that mean outdated
   is added.
3. Draw the note with the old value stored, and decline with the count if it cannot reach the
   draws.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
- 2026-11-24: a rule keeping the tool on a stated value of one lowercase word kept the nine
  messages above, and was drawn on the card with the old value stored: on a new value of the same
  shape it deleted the old row in 3 of 32 draws, against 0 of 32 with the refusal, so the refusal
  stays and the cost side stays open
  ([readings](../../readings/forget-refusal-stated-fact.md#a-value-of-one-lowercase-word-2026-11-24)).
- 2026-11-26: step 1 drawn with the old value seeded, 8 draws per message, every card approved:
  `Retiens que ce code est périmé.` refused a call in 1 draw, `Merk dir, dass der Code ungültig
  ist.` and `Recuerda que el código está caducado.` in 3 each; no old row deleted, the new message
  stored in all 24, no note shown. By the rule written before the draw the cost is real on the
  German and Spanish messages, and step 2 is next.
- 2026-11-26: meets the bar of the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): it rests on seeded live draws of messages a person types, 7 of 24 with a refused call, and its remedy is a note shown on a refused call; the fallback that kept the tool on these messages widened a reader and is removed from step 2.
