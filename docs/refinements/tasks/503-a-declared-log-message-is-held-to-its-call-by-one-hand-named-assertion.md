# A declared log message is held to its call by one hand named assertion

**Status:** landed 2026-08-30
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-30 by the close of
[R-491](491-the-guard-holding-a-declared-logger-to-its-call-names-two-sinks-by-hand.md), which
derived the logger half of this question and left the word beside it exactly where the logger used
to be.

The tool audit's sink binds `_MESSAGE = "tool.invocation"` and hands that binding to
`_logger.info`. An identifier says nothing about the string inside it, so a call passing a different
literal is two words rather than one spelled twice, and the constant registry goes on tying the
runbook sentence and the process entry's suite to the declaration while the brain writes the other
word. What refuses that today is one place: `brain/packages/tools/tests/test_audit.py` asserts four
whole rendered lines, and the registry names that assertion so it cannot be deleted in silence
(ADR-0009 declared-name addendum). It is one sink's own suite, named by hand, which is the shape
the logger half was in this morning.

**A second sink declaring a message is held by nothing.** The recall trail spells its word inside
the call, so it has no declaration to lose; a third sink written the way the tool audit is written
would carry a `_MESSAGE` the documents could be tied to and no assertion anywhere holding it to the
call, and every gate would be green.

**Why the logger's answer does not transfer.** The logger half was derived because
`logcalls.loggers` already answers with the name the CALL carries, in every spelling a call can
carry it, so the tree could be asked which sinks named themselves. There is no such reader for a
message. `logcalls.logged` finds a call by matching a literal first argument, which is precisely
what a sink handing its call an identifier does not write, so today's reader cannot confirm that a
declared message reaches its own call at all.

**What would close it.** Weigh whether the reader should learn the identifier spelling the logger
side already reads, resolving a bare name against the module's own top level through
`moduleconstants.py`, which would let a guard hold every module binding a message to the call
receiving it, the same set comparison the logger half now makes. Weigh against that what the sample
gate wants: `logged` is `samplecheck.py`'s way of finding the call a documented line claims, and a
sample quotes a rendered message, so teaching it to match an identifier means deciding what a
sample of such a line would even be. This is a different question from
[R-490](490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md), which is
about one module spelling its own message twice; that rule reads one module's text, where this one
is about what the call really carries.

## Trail

- 2026-08-30: opened by the close of
  [R-491](491-the-guard-holding-a-declared-logger-to-its-call-names-two-sinks-by-hand.md), whose
  mutation table measures a third self-named sink going from unheld to held for its logger and says
  nothing about a message.
- 2026-08-30: **landed** as the reader half, worked together with
  [R-490](490-a-declared-log-message-may-be-spelled-again-in-the-call-that-logs-it.md) (ADR-0009
  handed-message addendum). Re-derivation moved this entry twice. The third sink it supposed is
  already five calls in three modules, `cortex_tools/audit.py`, `cortex_orchestrator/abandon.py`
  and `cortex_core/brain_phase.py` with three of its own, and two of the four outside the tool
  audit are held firmly by suites that import the constant and assert the emitted record against
  it, which no gate arranged and nothing states. And the reader's blindness was not a gap but a
  live fault: `logged` answered `audit.py logs no message 'tool.invocation'` about the module that
  logs it, so a runbook printing a rendered sample of any of those five lines failed
  `check-samplecheck` as a message no module writes. That is what landed. The reader now resolves a
  bare name against the module's own top level through `moduleconstants.py`, the reading
  `loggernames.py` already made of a logger claimed the same way, and the question this entry
  raised about what a sample of such a line would be has one answer: the same sample as any other,
  since the formatter renders the string and never the expression that carried it.
  What did **not** land is the set comparison this entry hoped for, and the reason is measured
  rather than argued: the brain binds about twenty top-level strings whose names say `MESSAGE` or
  `MSG` and only five are log messages, the rest being model-facing refusals, so there is no
  `_LOGGER_NAME` for a message and a convention introduced to make one would redden every one of
  them. That residue is [R-504](504-a-declared-message-and-a-different-word-in-the-call.md), which
  carries the two paths worth weighing. Printing the lines this now makes printable is
  [R-505](505-the-spill-line-a-runbook-describes-and-never-prints.md).
