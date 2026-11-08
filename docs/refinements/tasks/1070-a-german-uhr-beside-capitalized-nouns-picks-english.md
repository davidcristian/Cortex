# A German Uhr beside capitalized nouns picks English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`message_language` in `note_language.py` skips a capitalized word beside another capitalized word
inside a sentence, so that `Las Vegas` and `Le Bernardin` name no language. German capitalizes
every noun, so `Uhr` beside nouns is skipped too. Unit probes on 2026-11-08 against `6c2cf4f9c`:
`Termin Montag 9 Uhr` picked `de` before that change and `en` after it, while
`Zahnarzt Montag um 9 Uhr` and `Morgen 9 Uhr Zahnarzt` still pick `de`. The note falls back to
English, the safe side of ADR-0076, but a German note was due. No recorded draw message has this
form ([the readings](../../readings/closing-note-language.md)).

## What to do

1. Write the German noun forms as tests first (`Termin Montag 9 Uhr`, `Arzt Freitag 10 Uhr`) beside
   the English names that must still be skipped.
2. Count `Uhr` after a clock figure whatever its neighbours, or read a name only from words that
   no list holds, then replay every recorded draw message through the old and new picker.

## History

- 2026-11-08: filed when names and abbreviations stopped counting toward a note language, from
  unit probes of German messages with no function word.
