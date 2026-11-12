# A request to remember an action stated after que, dass or că refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`forget_unrequested` (`forget_unrequested.py`) reads the letters of French, German, Spanish and
Romanian only on a request that `asks_kept_fact_other` (`memory_request.py`) reads as one stated
fact, which it takes from `que`, `dass` or `că` after the remember verb
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
The clause after that word can ask the assistant for an action instead of stating a fact. When
its verb is in no list, the message returns `{"forget_memories"}` and the person needs a second
message to have the row forgotten. Each of these is refused at HEAD, and the start build
`d1620de90` kept those marked "kept" by an accented letter:

- `Recuerda que remuevas mi código.` (kept)
- `Recuerda que debes tirar mi código.`, `Recuerda que tienes que desechar mi código.` (kept)
- `Ține minte că trebuie să arunci codul meu.`, `Ține minte că vreau să arunci codul.` (kept)
- `Souviens-toi que tu dois jeter mes données de santé.` (kept)
- `Souviens-toi que tu dois jeter mon code.`, `Souviens-toi que je veux que tu jettes mon code.`
- `Merk dir, dass du meinen Code wegwerfen sollst.`

A clause holding a negation or a listed verb keeps the tool: `Souviens-toi que mon code n'est plus
7319.`, `Merk dir, dass du den alten Code löschen sollst.`, `Recuerda que ya no quiero que
guardes mi código.` and `Ține minte că nu mai vreau să păstrezi codul.` all do. A new value with
no such word (`Merk dir, dass mein neuer Code 4826 ist.`, `Recuerda que mi código ahora es 4826.`)
is refused as `Remember that my new code is 4826.` is in English, which is the measured design in
[forget-refused-stated-fact](../../readings/forget-refused-stated-fact.md), so it is not part of
this task.

The same reader keeps the tool on facts it cannot place, a loss of the refusal rather than of a
row, since the card still asks first: `Merke dir, mein Code ist 4417.` (a comma and no `dass`) and
`Merke dir: mein Gewicht ist 72,5 kg.` (a colon), which the start build refused.

## What to do

1. Count the forms in recorded draws first: no recorded draw has any of them, so draw one per
   language before building.
2. Do not add verbs. Choose a reader from the form only: a clause addressed to the assistant, by
   a second person pronoun (`tu`, `du`, `te`), a second person verb ending after `que` or `să`,
   or a modal of obligation or wish before an infinitive or `să` (`dois`, `sollst`, `debes`,
   `tienes que`, `trebuie să`, `vreau să`). Write near-miss facts as tests before the code:
   `Recuerda que tienes cita a las 9.`, `Recuerda que las llaves están en el coche.`, `Ține minte
   că trebuie să plec la 9.`, `Merk dir, dass meine Schwester Vegetarierin ist.`
3. Replay every recorded draw message and test string through the start build, HEAD and the new
   reader, and name every string whose result changes.

## History

- 2026-11-12: filed when the four languages' letters became read only on a stated fact, which
  kept the tool on requests to remember an action and left this form refused.
