# A request to remember a named source with no file word refuses the file tools

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-11-05

`_SOURCE` (`unasked_tools.py`) reads a question, a path, a link or a source word, and since
2026-11-05 also `Downloads`, `downloaded`, `readme` and `attached`, so `Remember the report in
Downloads.`, `Remember the first paragraph of the readme.` and `Remember the attached contract` keep
the file tools ([readings](../../readings/sidecar-tools-on-remember.md#word-forms-of-a-source-2026-11-05)).
It still refuses them on a record noun with no source word: `Remember the numbers in my budget
sheet.`, `Remember my resume`, and the M rows of that record.

A wrong read is not free either. `Remember the meeting on my birthday.` (W01) called a file tool in 3
of 4 draws once the reader kept the tools, and a file call keeps the turn out of memory. So a plain
list of document nouns is the wrong remedy: it also reads `Remember that my report is due on Friday.`.
The reader that reads a record word only in "the X from, on or in my Y" was drawn and reverted on a
reply claim `claims_kept` did not read then
([draws](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)).
`claims_kept` reads that reply now.

## What to do

Rebuild that record-word reader from its readings (its patch was in a scratchpad lost to a reboot),
add `sheet`, `report` and `resume` to its record words with near misses first, replay the recorded
messages, and draw its rule again.

## History

- 2026-10-31: filed from the night's closing audit.
- 2026-11-05: corrected. The word forms are read now; a wrong read here also loses the fact, so the
  document nouns wait on the record-word reader's rule.
