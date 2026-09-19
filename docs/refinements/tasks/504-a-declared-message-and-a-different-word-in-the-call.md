# A declared message and a different word in the call

**Status:** done 2026-09-02
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`brain/packages/tools/src/cortex_tools/audit.py` binds `_MESSAGE = "tool.invocation"` and hands it
to `_logger.info`. The constant registry compares the tools runbook and the process entry's logging
suite with that binding, so a call passing some other literal leaves three documents restating a
word the brain does not write. That is two words rather than one written twice, which the rule
against a doubled name sees and lets through. What catches it is
`brain/packages/tools/tests/test_audit.py`, which asserts four whole rendered lines, and the
registry names that assertion so it cannot be deleted without a failure (ADR-0045 decision 15). One
package's own suite, named by hand.

The logger's derivation does not transfer, measured rather than assumed. That test reads a
structural set off the calls, a logger that is not its module's dotted path being a self-named sink,
and requires it to equal the names brain modules bind under `_LOGGER_NAME`. A message has no such
naming: the brain binds about twenty top-level strings whose names say `MESSAGE` or `MSG` and only
five are log messages; the rest are model-facing refusals (`BUDGET_EXHAUSTED_MSG`, `DENIED_MSG`,
`TAINTED_TASK_MSG` and a dozen more in `brain/packages/core/src/cortex_core/`).

Two options were weighed. The cheaper uses the registry's own vocabulary: a `Mention` may render
`{name}` as well as `{value}`, so the audit message's entry could include a mention of the emitting
call rendering the identifier, `_logger.info({name},`, and a call passing another word fails
`check-crosscheck`. The other gives the registry a way to say which of its values is a log message,
compared against the sites a log call is handed, which is a change to `couplings.py` and a field no
scan reads.

## History

- 2026-08-30: opened by the close of
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), whose
  mutation table measures the doubled name going from passing to three failures and says nothing
  about a call using a different word.
- 2026-09-02: closed as the cheaper option with the test it needed (ADR-0045 decision 14). Every
  claim about the sink held, and one was overtaken: the no-reading message is covered by
  `check-samplecheck` since the runbook printed it (ADR-0045 decision 10), so three of the four other
  declared messages are covered rather than two, and only the decode reading's is covered by
  nothing. The registry's rule that a used name must be declared now reads the sites as declaring
  the names they bind; the tool audit's entry has a mention of the emitting call,
  `_logger.info({name},`; and
  `test_every_registered_binding_a_brain_log_call_is_handed_is_held_at_that_call` requires such a
  mention, on the call's line, of every registry site a brain log call is handed, a set read off the
  registry and `logcalls.handed` together rather than off any naming, which is why the marker field
  was declined again. The suite convention covering the other messages is written down and not
  checked, a binding no document restates having no second place to disagree with. Opened:
  [R-518](518-a-registered-binding-handed-at-a-wrapped-call-has-no-one-line-needle.md) for a binding
  handed at a call the formatter wraps, and
  [R-519](519-a-runbook-restates-a-declared-message-as-a-wrapped-prefix-nothing-ties.md) for the
  spill warning's message.
