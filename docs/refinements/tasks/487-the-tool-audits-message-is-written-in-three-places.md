# The tool audit's message is written in three places and checked nowhere

**Status:** done 2026-08-29
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`tool.invocation` is the message every audited dispatch writes, the first argument of the
`_logger.info` call in `brain/packages/tools/src/cortex_tools/audit.py`. It is restated by
[tools-mcp.md](../../runbooks/tools-mcp.md), which tells an operator that the line is a bare
`tool.invocation` message followed by its fields, and written again by
`brain/packages/orchestrator/tests/test_config_logging.py`, which logs it under this trail's name.
Rename it in the sink and the runbook describes a message nothing writes while that suite goes on
passing, having renamed with itself.

`samplecheck.py` compares a documented log line with the call that writes it, message included, but
only where a runbook prints a rendered line. This runbook describes the line in prose, so this trail
is invisible to that check.

## History

- 2026-08-28: opened by the close of
  [R-486](486-the-tool-audits-logger-name-is-written-in-four-places.md), whose
  registry entry states in its own docstring that this word is compared with nothing.
- 2026-08-29: closed, as [ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 14 and a
  fifth entry in `scripts/trailcouplings.py`. The sink declares `_MESSAGE` beside `_LOGGER_NAME` and
  hands it to the emitting call, and the three restatements are compared with it: the runbook
  sentence and the level suite's two copies. The three options were settled by measurement rather
  than by taste. A rendered sample in tools-mcp.md, which would have brought the whole sample check
  to bear at once, was tried on the committed tree first: `just check-samplecheck` failed on it,
  because this sink builds its `extra=` across statements and by condition and `logcalls.py` will
  not read a field list off such a call. A line whose fields are chosen at runtime has no single
  field list to print, so no runbook may contain one of these as a checked sample, which is recorded
  on [R-444](444-nothing-says-which-log-lines-a-runbook-should-print.md). Doing nothing was declined
  because the runbook sentence tells a reader what to look for, which is an instruction. The entry's
  count was right and its neighbour needed relaxing: three places, four copies, and
  `brain/packages/tools/tests/test_audit.py` is deliberately not a fourth, since it asserts the
  rendered line rather than writing the message. The logger entry's search text on the level suite's
  asserted line used to write this word as fixed text, so each search text now renders its own half
  of `LEVEL:logger:message`. Opened by this close:
  [R-490](490-a-declared-log-message-may-be-written-again-in-the-call.md), from a
  mutation that measured zero.
