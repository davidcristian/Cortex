# A French message with no accent whose one word is ce gets Romanian notes

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-28

`message_language` (`note_language.py`) counts one word of `Note ce code: 5530.`, the Romanian
`ce`. French also writes `ce` (`_ALSO_WRITTEN`), but the message holds no letter outside ASCII, so
the letters do not decide between the two and the closing notes of such a turn are Romanian. The
Romanian `Ce faci?` reads the same way and keeps its Romanian note, so no reading of the message's
letters tells the two apart ([readings](../../readings/note-language-letter-tie.md)).

## What to do

1. Find a reading that tells such a message apart without a word in a list `forget_language`
   reads, since the forget message readers read that pick and are frozen
   ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7). One candidate is the
   language of the reply, read only when the message's pick rests on one word two languages write
   and on no letter.
2. Replay the recorded messages and replies through the old and new pick and state every change,
   or decline the task when no reading separates the two forms.

## History

- 2026-11-28: filed from [R-1380](1380-a-french-message-whose-one-counted-word-is-ce-gets-romanian-notes.md),
  whose rule reads the accented French messages and leaves this one Romanian.
