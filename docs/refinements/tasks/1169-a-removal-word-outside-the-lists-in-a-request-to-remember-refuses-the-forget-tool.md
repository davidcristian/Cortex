# A removal word outside the lists in a request to remember refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

On a message that `asks_kept_other` reads as a request to remember in French, German, Spanish or
Romanian, `forget_unrequested` (`forget_unrequested.py`) keeps the forget tool only on a word of
its lists, a negation or a letter outside those languages and English
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
A request that names removal by another word has the tool refused, which costs the person a
second message. Each of these returns `{"forget_memories"}`:

- `Ține minte să arunci codul.` and `Recuerda que remuevas mi código.`, which the start build
  `d1620de90` kept by their accented letters.
- `Merk dir, den Code wegzuwerfen.`, `Merk dir: weg mit meinem alten Code.` and
  `Souviens-toi : jette mon code.`, which the start build refused too. German `alt` is in no
  list, though `ancien`, `antigu` and `vechi` are.

## What to do

1. Write the messages above as tests that keep the tool, beside near-miss statements with the
   same words and no request (`Merk dir, dass ich den Code weggeworfen habe.`).
2. Choose the shape before adding words: a remember verb followed by an action (`să` or `de`
   with a verb, `zu` with an infinitive) asks for something done rather than states a fact, so a
   reader that keeps the tool on that form may replace a longer list. It also keeps the tool on
   `Ține minte să cumperi pâine.`; count such requests in the recorded draws before choosing.
3. Replay every recorded draw message and test string through the old and new reader, and name
   every string whose result changes.

## History

- 2026-11-12: filed from the audit of the four languages' letter reader, which fixed the
  Romanian `uiți` and `scoți` forms and left the words above.
