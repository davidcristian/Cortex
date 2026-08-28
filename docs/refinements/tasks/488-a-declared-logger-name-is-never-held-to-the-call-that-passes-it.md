# A declared logger name is never held to the call that passes it

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-28 by the close of
[R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), by a
mutation that was written to be a red row and measured zero.

Both self-named sinks now bind `_LOGGER_NAME` and hand it to `logging.getLogger`, and the constant
registry ties the documents restating that name to the binding. Nothing ties the binding to the
call. A sink that keeps `_LOGGER_NAME = "cortex.tools.audit"` and writes
`logging.getLogger("cortex.tools.audit")` again is green in every suite and every scan, and it
holds two names where there was one: `scripts/crosscheck.py` compares the documents against the
binding, `scripts/logcalls.py` reads the real name off the call, and the day the call's literal
moves the documents are held to a name the brain no longer writes. That is the silence the whole
close was against, one hop further in.

The reach is both sinks and any sink named this way later, so this is a rule about the shape rather
than about either trail.

**What would close it.** `logcalls.py` already parses each `getLogger` call and resolves a bare
identifier through `moduleconstants.py`, so it knows both halves at the point where a mismatch is
visible: it could refuse a module that binds a name matching the declaration convention and then
calls `getLogger` with a literal. Weigh first whether that belongs there or in the constant scan,
which is the module that cares about declarations, and whether the rule is "a module binding
`_LOGGER_NAME` must pass it" or the narrower "a module must not spell one logger name twice". The
narrow one is checkable without naming a convention and catches the same mutation.

## Trail

- 2026-08-28: opened by the close of
  [R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md), whose
  mutation table records the zero this entry is named for.
