# A declared log message is compared with its call by one hand-written assertion

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

The tool audit's sink binds `_MESSAGE = "tool.invocation"` and hands that binding to `_logger.info`.
An identifier says nothing about the string inside it, so a call passing a different literal is two
words rather than one written twice, and the constant registry goes on comparing the runbook
sentence and the process entry's suite with the declaration while the brain writes the other word.
What catches that is one place: `brain/packages/tools/tests/test_audit.py` asserts four whole
rendered lines, and the registry names that assertion so it cannot be deleted without a failure
(ADR-0045 decision 15). It is one sink's own suite, named by hand.

The logger's answer does not transfer. The logger half was derived because `logcalls.loggers`
already answers with the name the call passes, in every form a call can write it. There is no such
reader for a message: `logcalls.logged` finds a call by matching a literal first argument, which is
exactly what a sink handing its call an identifier does not write.

## History

- 2026-08-30: opened by the close of
  [R-491](491-the-guard-holding-a-declared-logger-to-its-call-names-two-sinks-by-hand.md), whose
  mutation table measures a third self-named sink going from unchecked to checked for its logger and
  says nothing about a message.
- 2026-08-30: closed as the reader half, worked together with
  [R-490](490-a-declared-log-message-may-be-written-again-in-the-call.md) (ADR-0045
  decision 8). Checking the premise moved this entry twice. The third sink it supposed is already
  five calls in three modules, `cortex_tools/audit.py`, `cortex_orchestrator/abandon.py` and
  `cortex_core/brain_phase.py` with three of its own, and two of the four outside the tool audit are
  covered by suites that import the constant and assert the emitted record against it, which no
  check arranged and nothing states. And the reader's blindness was a live fault: `logged` answered
  `audit.py logs no message 'tool.invocation'` about the module that logs it, so a runbook printing
  a rendered sample of any of those five lines failed `check-samplecheck` as a message no module
  writes. That is what was fixed. The reader now resolves a bare name against the module's own top
  level through `moduleconstants.py`, the same reading `loggernames.py` already made of a logger,
  and the question about what a sample of such a line would be has one answer: the same sample as
  any other, since the formatter renders the string and never the expression that produced it. What
  did not happen is the set comparison this entry hoped for, for a measured reason: the brain binds
  about twenty top-level strings whose names say `MESSAGE` or `MSG` and only five are log messages,
  the rest being model-facing refusals, so there is no `_LOGGER_NAME` equivalent for a message. That
  residue is [R-504](504-a-declared-message-and-a-different-word-in-the-call.md). Printing the lines
  this makes printable is [R-505](505-the-spill-line-a-runbook-describes-and-never-prints.md).
