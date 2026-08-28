# The tool audit's message is spelled in three places and held in none

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-28 by the close of
[R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), which held
this trail's logger and left the word beside it on the same line alone.

`tool.invocation` is the message every audited dispatch writes, the first argument of the
`_logger.info` call in `brain/packages/tools/src/cortex_tools/audit.py`. It is restated by
[tools-mcp.md](../../runbooks/tools-mcp.md), which tells an operator that the line is "a bare
`tool.invocation` message followed by its fields" and so is how a reader knows what to look for,
and written again by `brain/packages/orchestrator/tests/test_config_logging.py`, which logs it
under this trail's name to prove that the shipped level is not a knob. Rename it in the sink and
the runbook describes a message nothing writes while that suite goes on passing, having renamed
with itself.

**Why the sample gate does not already cover it.** `samplecheck.py` holds a documented log line to
the call that writes it, message included, but only where a runbook prints a rendered line. This
runbook describes the line in prose instead, so this trail is invisible to that gate: the sample
count it reports covers three lines and none of them is this one. That is the coverage question
[R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md) is filed for, and it is a
different question from agreement, which is why this entry is not a duplicate of it.

**What would close it, and what to weigh first.** The recall trail's message is held because a
reader outside the brain declares it, which this trail has no equivalent of: the declaration would
have to be a second module constant in the sink, and a constant added for the gate's benefit is a
cost this repo pays only with an argument, which the logger's own close made and did not make
twice. So weigh three options before building. A `_MESSAGE` constant beside `_LOGGER_NAME`, one
registry entry and two mentions, which is the shape the logger took. Or a rendered sample in
tools-mcp.md, printing one real line, which brings the whole sample gate to bear on the message,
the level, the logger and the fields at once, and costs a captured line that has to stay honest.
Or nothing, if the runbook's prose is judged to be about the trail rather than a quotation of it.

## Trail

- 2026-08-28: opened by the close of
  [R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), whose
  registry entry states in its own docstring that this word is held by nothing.
