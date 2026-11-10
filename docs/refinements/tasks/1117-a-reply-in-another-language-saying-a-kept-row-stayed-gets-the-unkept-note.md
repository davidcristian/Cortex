# A reply in another language saying a kept row stayed gets the unkept note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-10

`unkept_note_due` (`memory_claim.py`) leaves out an English keep claim whose only object is a row
the turn's forget kept (`names_spared`), and reads `claims_kept_other` with no such exception. A
forget with a keep clause in Spanish or Romanian whose reply says the spared row was kept therefore
ends with `UNKEPT_CLAIM_NOTE`, which tells the person to send again a fact that is still stored.
Unit reproduction, `forget_called=True`, the spared row `User: Remember my gym code 5521.`:

| Message | Reply | Note |
| --- | --- | --- |
| `Forget my bank PIN but keep my gym code.` | `I've deleted your bank PIN and kept your gym code.` | no |
| `Olvida mi PIN del banco pero guarda mi código del gimnasio.` | `He borrado tu PIN del banco y he guardado tu código del gimnasio.` | yes |
| the same | `He borrado tu PIN del banco; tu código del gimnasio queda guardado.` | yes |
| `Uită PIN-ul de la bancă, dar păstrează codul de la sală.` | `Am șters PIN-ul de la bancă și am salvat codul de la sală.` | yes |

None of these messages reads as a request to keep (`asks_kept` is false), so the reply claim alone
makes the note due. The note states only that nothing of the message was kept, which is true; the
cost is a person sending a stored fact again, not a lost fact.

## What to do

1. Draw the Spanish keep clause flow 4 times on the stack before deciding, and count replies that
   claim the spared row was kept.
2. If the form occurs, write near misses first (a new value claimed kept beside a spared row, a
   question, a negation) and give `names_spared` the keep verbs of `claims_kept_other`
   (`guardado`, `salvat`, `gardé`, `behalten`), replaying every recorded reply string through
   both readers. The note's safe side is to show, so a reply naming any fact beyond a spared row
   keeps it.

## History

- 2026-11-10: filed from the audit of the reply readers built that night.
