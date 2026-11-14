# A request to remember that a value is outdated refuses the forget tool outside English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

`forget_unrequested` keeps the forget tool when a word of `RETRACT_WORDS` can retract a stored
fact. English reads `outdated`, `obsolete`, `stale` and `wrong`, so `Remember that the number is
outdated.` keeps it. The French, German, Spanish and Romanian words for the same thing are not in
the list, and `asks_kept_fact_other` reads each message below as a stated fact, so each is refused
on the start build of 2026-11-14 and on HEAD (`forget_unrequested` alone, no model):
`Merk dir, dass die Nummer veraltet ist.`, `Merk dir, dass der Code ungültig ist.`, `Merk dir,
dass der Termin abgesagt ist.`, `Retiens que ce code est périmé.`, `Retiens que mon adresse est
fausse.`, `Recuerda que ese número ya es viejo.`, `Recuerda que el código está caducado.`, `Ține
minte că numărul acela e expirat.` and `Ține minte că parola e invalidă.`.

## What to do

1. Write tests first: each message above keeps the tool, and `Retiens que mon code est 5528.`
   stays refused.
2. Prefer a change of shape to more words: for example, a stated fact whose value is one word and
   holds no digit or capital in these four languages keeps the tool, since such a value often
   describes the old fact rather than giving it a new value. Replay the shape on the facts it must
   still refuse (`dass meine Schwester Vegetarierin ist`).
3. Replay every string literal of the brain's tests and every backticked string of `docs/` through
   both builds, and count refusals newly dropped.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
