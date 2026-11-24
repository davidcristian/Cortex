# A request to remember that a value is outdated refuses the forget tool outside English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

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

1. Draw the cost side first, with the rule written before the first draw: seed an old value, then
   send `Retiens que ce code est périmé.` and two other messages above, 8 draws each, every card
   approved, and count the old row deleted, the new message stored and the old value note shown.
   A refused call costs the person one more message, which the old value note asks for when it
   shows.
2. Only if that cost is real, write tests first: each message above keeps the tool, and
   `Retiens que mon code est 5528.`, `Souviens-toi que mon vélo est bleu.` and `Recuerda que soy
   vegetariano.` stay refused. Do not add a word list of words that mean outdated, and do not key
   the rule on the value's shape alone.
3. Replay every string literal of the brain's tests and every backticked string of `docs/` through
   both builds, count refusals newly dropped, and draw any new value the change keeps with its old
   value stored.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
- 2026-11-24: a rule keeping the tool on a stated value of one lowercase word kept the nine
  messages above, and was drawn on the card with the old value stored: on a new value of the same
  shape it deleted the old row in 3 of 32 draws, against 0 of 32 with the refusal, so the refusal
  stays and the cost side stays open
  ([readings](../../readings/forget-refusal-stated-fact.md#a-value-of-one-lowercase-word-2026-11-24)).
