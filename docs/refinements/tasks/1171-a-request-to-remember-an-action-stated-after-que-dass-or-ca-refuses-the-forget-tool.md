# A request to remember an action stated after que, dass or că refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`forget_unrequested` (`forget_unrequested.py`) reads the letters of French, German, Spanish and
Romanian only on a request that `asks_kept_fact_other` (`memory_request.py`) reads as one stated
fact, which it takes from `que`, `dass` or `că` after the remember verb
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
A fact clause holding an obligation of the assistant or a second `que tu` (`tu dois`, `il faut`,
`debes`, `hay que`, `trebuie`, `să`, `sollst`, `musst`) is read as a request for an action and keeps
the tool. Four forms that ask for an action hold none of those words and are still refused, so the
person needs a second message to have the row forgotten:

- `Recuerda que remuevas mi código.` and `Recuerda que tires mi código.`: a Spanish second person
  subjunctive straight after `que`. The start build `d1620de90` kept both by their accented letter.
- `Souviens-toi que tu jettes mon code.`: `tu` straight after the opening `que`.
- `Merk dir, dass du meinen Code wegwirfst.`: `du` with a finite verb.
- `Tine minte ca vreau sa arunci codul.`: Romanian with no diacritics, where `sa` is also French.

The start build and HEAD refuse the last three as well. Each marker for them is a pronoun or an
ending that also opens a stated fact (`Recuerda que tienes cita a las 9.`, `Souviens-toi que tu es
né en 1990.`, `Souviens-toi que sa voiture est rouge.`), so no closed word separates them.

## What to do

1. Count the forms in recorded draws first: no recorded draw has any of them, so draw one per
   language before building.
2. Do not add verbs or verb endings. If the draws show a form, prefer a brain-appended note on a
   refused forget call over a wider reader.
3. Replay every recorded draw message and test string through the start build, HEAD and the new
   reader, and name every string whose result changes.

## History

- 2026-11-12: filed when the four languages' letters became read only on a stated fact with
  no obligation of the assistant, which left these forms refused. No draw was made, since the
  stack was down.
