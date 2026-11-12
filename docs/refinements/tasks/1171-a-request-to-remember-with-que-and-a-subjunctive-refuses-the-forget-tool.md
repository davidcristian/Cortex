# A request to remember with que and a subjunctive refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`forget_unrequested` (`forget_unrequested.py`) reads the letters of French, German, Spanish and
Romanian only on a request that `asks_kept_fact_other` (`memory_request.py`) reads as one stated
fact, which it takes from `que`, `dass` or `că` after the remember verb
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
Spanish `que` can also open a request with a subjunctive, so `Recuerda que remuevas mi código.`
returns `{"forget_memories"}`, which the start build `d1620de90` kept by its accented letter. The
person needs a second message to have the code forgotten.

The same reader keeps the tool on facts it cannot place, a loss of the refusal rather than of a
row, since the card still asks first: `Merke dir, mein Code ist 4417.` (a comma and no `dass`) and
`Merke dir: mein Gewicht ist 72,5 kg.` (a colon), which the start build refused.

## What to do

1. Count the forms in recorded draws first: no recorded draw has either form, so draw a request
   to remember with `que` and a subjunctive and one with a comma and no `dass` before building.
2. Do not add verbs. Choose a reader from the form only, such as a second person verb ending
   right after Spanish `que`, and write near-miss facts (`Recuerda que tienes cita a las 9.`,
   `Recuerda que las llaves están en el coche.`) as tests before the code.
3. Replay every recorded draw message and test string through the start build, HEAD and the new
   reader, and name every string whose result changes.

## History

- 2026-11-12: filed when the four languages' letters became read only on a stated fact, which
  kept the tool on requests to remember an action and left this form refused.
