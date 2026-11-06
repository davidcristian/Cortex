# A request to remember a named source with no file word refuses the file tools

**Status:** done 2026-11-06
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`_SOURCE` (`unasked_tools.py`) reads a question, a path, a link or a source word, and since
2026-11-05 also `Downloads`, `downloaded`, `readme` and `attached`, so `Remember the report in
Downloads.`, `Remember the first paragraph of the readme.` and `Remember the attached contract` keep
the file tools ([readings](../../readings/sidecar-tools-on-remember.md#word-forms-of-a-source-2026-11-05)).
It refused them on a record noun with no source word: `Remember the numbers in my budget sheet.`,
`Remember my resume`, and the M rows of that record.

A wrong read is not free either. `Remember the meeting on my birthday.` (W01) called a file tool in 3
of 4 draws once the reader kept the tools, and a file call keeps the turn out of memory. So a plain
list of document nouns is the wrong remedy: it also reads `Remember that my report is due on Friday.`.
The reader that reads a record word only in "the X from, on or in my Y" was drawn and reverted on a
reply claim `claims_kept` did not read then
([draws](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)).
`claims_kept` reads that reply now.

## What was done

`_RECORD` in `unasked_tools.py` reads "the X from, on or in my Y" as a source when Y is a record
word (`sheet`, `report`, `resume` and `cv` among them) and the message ends at Y, with the near misses
as tests first, a replay of 438 recorded requests (6 change, all of the shape) and 18 draws against a
rule written first, in [sidecar-tools-record-words.md](../../readings/sidecar-tools-record-words.md).
`Remember my resume` alone still refuses the tools, since no row supports reading it as a source.

## History

- 2026-10-31: filed from the night's closing audit.
- 2026-11-05: corrected. The word forms are read now; a wrong read here also loses the fact, so the
  document nouns wait on the record-word reader's rule.
- 2026-11-06: done. The record-word reader rebuilt, replayed and drawn: the two record rows read the
  file and stated its value in 6 of 6, W01 and three near misses stored the fact in 12 of 12 with no
  file call. The `photo` near miss that is a wrong keep already is task 992.
