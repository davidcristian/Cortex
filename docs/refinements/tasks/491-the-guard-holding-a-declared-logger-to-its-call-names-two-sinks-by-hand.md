# The guard holding a declared logger to its call names two sinks by hand

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-29 by the close of
[R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md), which went looking for a
rule and found the property already held by a test nobody had written for it.

What holds a sink's `_LOGGER_NAME` to the name its `getLogger` call really receives is
`test_the_committed_brain_declares_both_spellings_a_logger_is_claimed_in` in
`scripts/tests/test_logcalls.py`. It asserts that `logcalls.loggers` maps `cortex.tools.audit` to
`cortex_tools/audit.py` and `cortex.memory.recall` to `cortex_memory/audit.py`, and that reader
answers with the name the CALL carries, so a sink binding one name and passing another fails those
lookups. The close registered both spellings as couplings, so the guard can no longer be retargeted
or deleted in silence.

**Both names are written out by hand.** A third self-named sink is guarded by nothing until
somebody remembers to add a line, which is the shape
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s addendum on deriving the set a rule runs
over is against, and which `flagcheck.py` already solves next door by deriving its servers from the
stack's own wiring rather than reading a list. The set here is derivable the same way:
`logcalls.loggers` already returns every logger the brain declares against the file declaring it,
and a self-named sink is exactly a module whose top level binds a string that its own `getLogger`
call is handed. Nothing but the hand-written pair says which those are.

**What would close it.** Derive the set rather than list it: a module binding a name and passing
that binding to `getLogger` is a self-named sink by construction, so the guard could assert over
whatever the tree holds instead of over two literals. Weigh first whether that belongs in the suite
or in `logcalls.py` itself, since a rule there reaches every module and would need the split its own
docstring draws, the reader standing at exactly 300 lines; and weigh whether a derived guard still
leaves the registry a spelling to tie the documents to, which is what the two literals give it
today.

## Trail

- 2026-08-29: opened by the close of
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md), whose mutation table
  measures the guard catching both sinks and says nothing about a third.
