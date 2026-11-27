# A French message whose one counted word is ce gets Romanian notes

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-27

`message_language` (`note_language.py`) counts `ce` as a Romanian word, and the French list has
no word of `Retiens bien ce code périmé.`, `Retiens que ce code a changé.` or `Note ce code:
5530.`, so each reads as Romanian alone, with no tie for the letters to break, and every closing
note of such a turn is Romanian. `forget_language` reads them the same way. The letter tie of
[the readings](../../readings/note-language-letter-tie.md) does not reach them, and taking `ce` out
of the Romanian list costs `Uită ce am spus.` its Romanian note, as those readings say.

## What to do

1. Find why `retiens`, `bien` and `changé` count for no list, and decide on a rule for the note
   pick alone, such as letters counting when only one language scores a single word. A change to
   the word lists would also move `forget_language`, which the forget message readers read, and
   those readers are frozen ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7),
   so the rule must leave `forget_language` as it is.
2. Replay the recorded messages of the closing note language readings through the old and new
   pick, as the letter tie's replay did, and state every message whose language changes.

## History

- 2026-11-27: filed from the check of which messages tied before the letter tie.
