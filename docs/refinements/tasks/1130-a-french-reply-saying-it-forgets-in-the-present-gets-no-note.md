# A French reply saying it forgets in the present gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

On 2026-11-10 at 06:32 local, chat `s17-m6` on the shared stack sent `Mon collègue m'a dit « oublie
ça », mais garde en mémoire que la réunion est jeudi.`. No forget call ran and the row was kept,
which is right, but the reply said `J'oublie ce que vous venez de mentionner (le « ça »).` with no
note after it ([readings](../../readings/overlay-mentioned-words-flows.md)). 1 of 3 draws made the
claim; a second said `J'ai mis de côté le point précédent`.

`claims_forgotten_other` (`forget_claim_other.py`) reads a past participle after `j'ai`, `c'est`
or `est` (`oublié`, `supprimé`), not the present `j'oublie` or `je supprime`, so the note that
says nothing was forgotten did not show.

## What to do

1. Write near misses as tests first: `J'oublie souvent mes clés.` quoted from the person,
   `Je n'oublie rien.`, `Voulez-vous que j'oublie ...?`, `Je supprime le fichier ?` in a file
   reply. Replay every readings string through the old and new reader.
2. Read a first-person present `j'oublie` or `je supprime` with an object outside a question, a
   condition and a negation as a claim. Its safe direction is to show the note.

## History

- 2026-11-10: filed from the mentioned-words flows.
