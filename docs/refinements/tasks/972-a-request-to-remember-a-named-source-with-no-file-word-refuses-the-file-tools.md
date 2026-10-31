# A request to remember a named source with no file word refuses the file tools

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-31

`_SOURCE` (`unasked_tools.py`) reads a question, a path, a link or a source word, and
`\bdownload\b` does not read `Downloads`. Real turns with `readme.md` in the sidecar's folder:
`Remember the first paragraph of the readme.` made two `list_allowed_directories` calls that were refused,
the reply said `I can't find a "readme" file in the current directory`, which no tool checked, and the
turn was stored. `Remember the report in Downloads.` was refused once and asked for the file's name. The
reader also refuses `Remember the numbers in my budget sheet.`, `Remember my resume` and
`Remember the attached contract`. Run log `t2.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot7/`.

## What to do

Widen `_SOURCE` with plurals and common document nouns. Near-miss facts first, such as
`Remember that my report is due on Friday.`, which may keep the tools at no cost, and a replay of the
recorded messages through the old and new readers. A refusal here costs a second message and a false
statement about the file, while a wrong read only keeps the tools offered.

## History

- 2026-10-31: filed from the night's closing audit.
