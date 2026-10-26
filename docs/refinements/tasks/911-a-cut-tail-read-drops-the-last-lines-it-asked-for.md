# A cut tail read drops the last lines it asked for

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`LastLinesToolRegistry` (`tool_tail.py`) returns a file's real last lines for a `tail` read, and
`cut_result` (`tool_round.py`) then keeps the first `MAX_RESULT_CHARS` (6,000) characters of that
text. A `tail` read longer than that keeps the oldest of the lines asked for and drops the newest,
so the file's last line is not shown, while `RESULT_CUT_NOTE` tells the model to ask for the `tail`
lines it already asked for. A question about the end of a log is then answered from the wrong
lines.

Reproduction over fakes (2026-10-26): a fake `read_text_file` serving 500 lines of 160 characters,
wrapped in `LastLinesToolRegistry`, called with `tail` 100, and its result passed through
`result_message`. The message held line 401, the first line asked for, and not line 500, and the
note said only the first 5,956 of 16,099 characters fit.

## What to do

1. Let a result say which end to keep. A `tail` read keeps its end, cut at a line break, with a
   note that names how many of the lines asked for were left out and suggests a smaller `tail`.
2. Test a `tail` read past the limit and a `head` read past it over fakes.

## History

- 2026-10-26: filed from an audit of the tool result cut against the `tail` read.
