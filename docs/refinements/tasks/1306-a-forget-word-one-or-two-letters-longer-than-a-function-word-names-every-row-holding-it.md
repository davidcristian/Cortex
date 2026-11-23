# A forget word one or two letters longer than a function word names every row holding it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-23

Over the Spanish rows `Recuerda que el código del gimnasio es 4242.`, `Recuerda que mi tarjeta es
4111 1111 1111 4242.` and `Recuerda que mi tarjeta nueva es 5500 0000 0000 4242.`, in unit calls
through `ForgetChosenTool`, `Olvida el código del gimnasio que queda.` with the call text
`tarjeta` deletes both cards, which the message does not ask for. At the code before `extends`
it deletes none. `forget_named` (`forget_keep_named.py`) names a row by a word of a clause holding
a forget verb that names no row when the word less one or two letters is a word of the row's
request, and it compares every word of the request: `queda` less two letters is `que`, which every
Spanish row holds. `may_keep` (`forget_inside.py`) compares a longer word only with the words of a
request that are no function word ([readings](../../readings/forget-keep-any-reading.md)).

## What to do

1. Write the message above as a test first, beside a near miss a longer word still names, as
   `Forget all lockers.` beside the locker row.
2. Compare a longer word in `forget_named` with the words of the request less the function words
   of every note language, as `may_keep` does.
3. Replay the generator with a form for each language holding a word one or two letters longer
   than a function word of its rows. Count the rows newly listed and newly kept, and check
   the cost of `Oublie ce que je viens de dire.` beside German rows that
   [R-1286](1286-a-forget-naming-a-code-deletes-another-row-after-a-word-for-all-or-for-a-code-word-in-another-number.md)
   records again.

## History

- 2026-11-23: filed from the close of
  [R-1280](1280-a-word-naming-no-row-before-the-row-a-keep-clause-names-again-lists-it.md), whose
  probe found it.
