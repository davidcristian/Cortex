# A new value stated in another language with a word for now or new names no old value

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`_bare` (`memory_old_value.py`) drops `now` or `actually` at either end of a value, and
`_CHANGE_WORDS` lets `new`, `current` or `actual` stand before the fact words, in English only.
So `Mon code d'alarme est maintenant 5528.`, `Mein Alarmcode ist jetzt 5528.` and `Mon nouveau
code d'alarme est 5528.` beside a row of the same fact with `4826` name nothing, while `My alarm
code is now 5528.` names `4826`. The note only shows, so naming nothing is the safe direction
([readings](../../readings/old-value-other-languages.md)).

## What to do

1. Write the words of each language as tests first: `maintenant`, `jetzt`, `ahora` and `acum`
   before or after the value, and `nouveau`, `nouvelle`, `neuer`, `neue`, `nuevo`, `nueva`, `nou`
   and `nouă` beside the fact words, with the Romanian adjective after the noun (`codul meu nou`).
2. Keep each list in the language of the pattern that read the message, so a French word never
   counts in a German statement, and replay with the scripts in
   `~/.cache/cortex-run/2026-11-25/s2/replay/`: no English note may change.

## History

- 2026-11-25: filed when
  [task 1236](1236-a-new-value-of-a-fact-stated-in-another-language-names-no-old-value.md) read
  the statement in four more languages and left these words unread.
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): its remedy is a word list in each language, and its count is three probe statements. 3 of 3 probed statements name no old value ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
