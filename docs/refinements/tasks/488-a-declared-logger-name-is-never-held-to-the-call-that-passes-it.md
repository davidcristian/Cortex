# A declared logger name is never compared with the call that passes it

**Status:** done 2026-08-28
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

Both self-named sinks bind `_LOGGER_NAME` and hand it to `logging.getLogger`, and the constant
registry compares the documents restating that name with the binding. Nothing compares the binding
with the call. A sink that keeps `_LOGGER_NAME = "cortex.tools.audit"` and writes
`logging.getLogger("cortex.tools.audit")` again passes every suite and every scan, and it has two
names where there was one: `scripts/crosscheck.py` compares the documents with the binding,
`scripts/logcalls.py` reads the real name off the call, and the day the call's literal moves the
documents are compared with a name the brain no longer writes.

The rule is about the shape rather than either trail, so it reaches both sinks and any sink named
this way later.

## History

- 2026-08-28: opened by the close of
  [R-486](486-the-tool-audits-logger-name-is-written-in-four-places.md), whose
  mutation table records the zero this entry is named for.
- 2026-08-28: closed, as [ADR-0045](../../adr/ADR-0045-documented-log-lines.md) decision 8 and a
  rule in `scripts/logcalls.py`: a literal `getLogger` argument this module's own top level also
  binds fails the check, the failure naming every binding of it and asking the call to pass one. The
  claim held when checked again, which is not what the two closes before it found: the mutation was
  applied to the tool audit's sink on the committed tree and `crosscheck`, `samplecheck`, `ruff`,
  `pyright` and the 504 tests of the tools and orchestrator suites were all green under it, and the
  unused constant is not an unused import, so no linter sees one either. The narrow rule this entry
  recommended is the one built, and the two wider ones were declined for a reason worth keeping: a
  rule over the `_LOGGER_NAME` convention has to write that identifier in the check tree, which is a
  third copy of exactly the kind of thing this repo would then want compared, and making the
  constant scan aware of what a logger is would make the registry's data a place where a subject is
  decided. It reaches every module rather than the two sinks, so a sink named this way later is
  covered the day it is written. The reader now stands at exactly 300 lines, so the next rule it
  gains splits it. Opened by this close:
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md), the half a rule about one
  name written twice cannot see.
