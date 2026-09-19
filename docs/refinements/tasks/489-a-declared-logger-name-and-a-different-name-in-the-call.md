# A declared logger name and a different name in the call

**Status:** satisfied 2026-08-29
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

A module may no longer write one logger name twice: `scripts/logcalls.py` fails on a literal
`getLogger` argument that the same module's top level also binds. What it cannot see is a module
binding `_LOGGER_NAME = "cortex.tools.audit"` and calling `getLogger("cortex.tools.other")`, which
is two names rather than one written twice. The constant registry then compares the runbooks, the
docstring and the suite with the declaration while the brain writes the other name.

Both wider rules were declined when the narrow one was built. Requiring a module that binds
`_LOGGER_NAME` to pass it makes the check tree write that identifier, which is a third copy of
exactly the kind of value this repo would then want compared, and making the constant scan aware of
what a logger is would put a subject inside the registry's data.

## History

- 2026-08-28: opened by the close of
  [R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md), whose mutation
  table covers one name written twice on both sinks and never asks which name the call passed.
- 2026-08-29: satisfied, and the sentence claiming the checks pass under this mutation is what did
  not survive. The mutation was applied to both sinks on the committed tree and `just check` fails
  for each: `scripts/tests/test_logcalls.py` has a test asserting that the brain declares
  `cortex.tools.audit` in the tool audit's sink and `cortex.memory.recall` in the recall trail's,
  and `logcalls.loggers` answers with the name the call passes, so a call passing another literal is
  a `KeyError` there. Beside it each sink's package suite asserts a whole rendered line, 13 failures
  in the tools package and 9 in the memory package. No rule was built, because the rule exists in
  effect. What shipped is the hardening that finding demands: the test's two copies and the audit
  suite's asserted message are registered in the constant registry, so a property covered by two
  accidents is now one the scan names, and neither can be retargeted or deleted without a failure.
  The reasoning is [ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 15. Opened by
  this close:
  [R-491](491-the-guard-holding-a-declared-logger-to-its-call-names-two-sinks-by-hand.md), since
  that test names its two sinks by hand.
