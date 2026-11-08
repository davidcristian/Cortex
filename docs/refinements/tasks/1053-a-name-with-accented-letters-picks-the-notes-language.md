# A name with accented letters picks the note's language

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-08

`message_language` in `note_language.py` counts every accented letter of a message as one point,
the same as a whole word from a language's list. Names with two or three such letters outweigh a
short English message: `Lunch with Jürgen Müller and Björn on Friday.` picks German, `Call José
María García López tomorrow` and `Dinner at Señor Muñoz's with María on Friday` pick Spanish,
`Remind me: Straße, Größe, Fußgänger at 9` German and `Remind me to visit Ștefan și Țuțu at 9`
Romanian. A reply to each is most likely English, so a due note would be in another language.
Loanwords alone held English in the probes (`rendez-vous`, `déjà vu`, `Champs-Élysées`, `crème
brûlée`), and `Fiesta mañana at 9` picks Spanish.

## What to do

1. Replay the 749 recorded replies' messages with letters counted once per word, and with letters
   counted only when no list word matched, against today's count.
2. Keep English as the fallback; the safe side is the English note under an unclear message.

## History

- 2026-11-08: filed by the second audit of the night's changes, from unit probes.
