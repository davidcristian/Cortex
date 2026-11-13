# A request to forget in another language written in a-z refuses the forget tool

**Status:** done 2026-11-13
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` (`forget_unrequested.py`) reads English, French, German, Spanish and Romanian
by its word lists and keeps the forget tool on any other message only by a letter outside `a-z`
([readings](../../readings/forget-refusal-other-languages.md)).
A request to forget in another language whose letters are all in `a-z` and that holds none of the
lists' words has the tool refused, which is a privacy loss. The start build `d1620de90` refuses it
the same way. Each of these returns `{"forget_memories"}`:

- Catalan: `Descarta el que et vaig dir de la meva salut.`
- Dutch: `Wis mijn adres.`
- Italian: `Svuota la memoria.`
- Portuguese without accents: `Tira o meu numero da memoria.`
- Norwegian and Finnish: `Glem det jeg sa om helsa mi.`, `Unohda puhelinnumeroni.`

## What to do

1. Write the messages above as tests that keep the tool, beside English requests to remember and
   questions that refuse it (`Remember that my sister is vegan.`, `What is my bike lock code?`).
2. Choose the shape before adding words: a reader that refuses only on a message it positively
   names as one of the five languages (English by its function words, the four others by the
   remember verbs `asks_kept_other` reads), or another language's forget verbs added list by list.
   The first keeps the tool on a short English message that names nothing, such as `Hi`; count
   those in the recorded draws before choosing.
3. Replay every recorded draw message and test string through the start build and the new reader,
   and name every string the new reader refuses that the start build kept.

## History

- 2026-11-12: filed from the replay of the reader that reads the four languages' letters only on
  a request to remember in one of them.
- 2026-11-13: done. The reader now refuses only a message it names as one of its five languages
  and reads as a request to remember or a question (`asks_kept_fact_other`, `asks_kept`, or a `?`
  or an opening question word beside an English word the other languages do not write alone), and
  every message above keeps the tool. No word was added to a list. Replayed with the start build
  over 32,826 strings, none is newly refused and 26,558 now keep the tool. Of the 854 short strings
  now kept that name no English word, a hand read finds 45 a person could send in English (11 in
  `docs/readings/`, 34 in tests), such as `Hi` and `Okay.`
  ([readings](../../readings/forget-refusal-other-languages.md#refusing-a-named-request-or-question-only-2026-11-13)).
