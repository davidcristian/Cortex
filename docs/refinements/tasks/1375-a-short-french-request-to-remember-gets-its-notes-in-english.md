# A short French request to remember gets its notes in English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0076](../../adr/ADR-0076-closing-note-language.md)
**Verified:** 2026-11-27

`message_language` (`note_language.py`) reads `Retiens que ce code est périmé.` as English, so
every closing note on that turn is written in English, `REFUSED_HELD_NOTE` included. It reads
`Retiens que mon adresse est périmée.` and `Oublie mon code.` as French. A French speaker then
reads the one note that tells them a remembered exchange still holds the value in a language they
did not write in.

## What to do

1. Find which words of the message `_counted` scores, and why no French word of `Retiens que ce
   code est périmé.` counts while `mon` does in the other two.
2. Replay the recorded messages of the closing note language readings through the old and new
   pick, and state every message whose language changes.

## History

- 2026-11-27: filed from the close of [task 1199](1199-a-request-to-remember-that-a-value-is-outdated-refuses-the-forget-tool-outside-english.md), whose History names this gap.
