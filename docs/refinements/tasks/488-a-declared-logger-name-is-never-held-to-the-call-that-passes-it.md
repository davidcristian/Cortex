# A declared logger name is never held to the call that passes it

**Status:** landed 2026-08-28
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-28 by the close of
[R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), by a
mutation that was written to be a failing row and measured zero.

Both self-named sinks now bind `_LOGGER_NAME` and hand it to `logging.getLogger`, and the constant
registry ties the documents restating that name to the binding. Nothing ties the binding to the
call. A sink that keeps `_LOGGER_NAME = "cortex.tools.audit"` and writes
`logging.getLogger("cortex.tools.audit")` again is green in every suite and every scan, and it
holds two names where there was one: `scripts/crosscheck.py` compares the documents against the
binding, `scripts/logcalls.py` reads the real name off the call, and the day the call's literal
moves the documents are held to a name the brain no longer writes. That is the failure nothing reports that the
whole close was against, one hop further in.

The reach is both sinks and any sink named this way later, so this is a rule about the shape rather
than about either trail.

**What would close it.** `logcalls.py` already parses each `getLogger` call and resolves a bare
identifier through `moduleconstants.py`, so it has both halves at the point where a mismatch is
visible: it could fail on a module that binds a name matching the declaration convention and then
calls `getLogger` with a literal. Weigh first whether that belongs there or in the constant scan,
which is the module that cares about declarations, and whether the rule is "a module binding
`_LOGGER_NAME` must pass it" or the narrower "a module must not spell one logger name twice". The
narrow one is checkable without naming a convention and catches the same mutation.

## Trail

- 2026-08-28: opened by the close of
  [R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), whose
  mutation table records the zero this entry is named for.
- 2026-08-28: **landed**, as the [ADR-0009 one-name
  addendum](../../adr/ADR-0009-tools-mcp.md) and a rule in `scripts/logcalls.py`: a literal
  `getLogger` argument this module's own top level also binds fails the gate, the fault naming every
  binding of it and asking the call to pass one. **The entry's claim held on re-derivation**, which
  is not what the two closes before it found: the mutation was applied to the tool audit's sink on
  the committed tree and `crosscheck`, `samplecheck`, `ruff`, `pyright` and the 504 checks of the
  tools and orchestrator suites were all green under it, and the unused constant is not an unused
  import, so no linter sees one either. The narrow rule the entry recommended is the one built, and
  the two wider ones were declined for a reason worth keeping: a rule over the `_LOGGER_NAME`
  convention has to spell that identifier in the gate tree, which is a third spelling of exactly the
  kind of thing this repo would then want tied, and making the constant scan aware of what a logger
  is would make the registry's data a place where a subject is decided. It reaches every module rather
  than the two sinks, so a sink named this way later is held on the day it is written. **The reader
  now stands at exactly 300 lines**, so the next rule it gains splits it, along the seam its own
  docstring already draws. Opened by this close:
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md), the half a rule about one
  name spelled twice cannot see.
