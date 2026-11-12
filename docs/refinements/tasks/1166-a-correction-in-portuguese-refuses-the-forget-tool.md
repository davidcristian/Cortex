# A correction in Portuguese refuses the forget tool

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

`forget_unrequested` (`forget_unrequested.py`) reads English, French, German, Spanish and Romanian
by its word lists, and keeps the forget tool on any letter outside those five languages
([readings](../../readings/forget-calls-on-remember-rise.md#the-refusal-in-four-more-languages)).
A message in another language written only in their letters is read by those lists. Portuguese
is the main such language: its forget verbs (`esqueça`, `apaga`) are listed, but its words of a
correction are not, so `Meu código mudou para 4862.` and `O meu código já é outro: 4862.` have
the forget tool refused, where a correction in the five languages keeps it. A Portuguese message
holding `não`, `ã` or `õ` keeps the tool through the letter clause.

Reproduction: `forget_unrequested("Meu código mudou para 4862.")` returns `{"forget_memories"}`.

## What to do

1. Write Portuguese corrections (`mudou`, `mudei`, `agora é`, `em vez de`, `já não`, `errado`,
   `antigo`) as tests that keep the tool, beside Portuguese requests to remember that refuse it.
2. Add the words to `RETRACT_WORDS`, or keep the tool on a message a language check reads as
   neither of the five languages, and replay every recorded message and test string through the
   old and new reader.

## History

- 2026-11-12: filed from the build that made the reader read French, German, Spanish and
  Romanian by words, whose probe of Portuguese found two corrections refused.
