# A declared log message may be spelled again in the call that logs it

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-29 by the close of
[R-487](487-the-tool-audits-message-is-spelled-in-three-places-and-held-in-none.md), which put a
second declaration in a sink and found the rule beside it stops one word short.

A module may no longer spell one **logger** name twice: `scripts/logcalls.py` refuses a literal
`getLogger` argument that the same module's top level also binds, which is the rule
[R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md) closed. Nothing
says the same about a **message**. `brain/packages/tools/src/cortex_tools/audit.py` now binds
`_MESSAGE` and hands it to `_logger.info`, and the constant registry ties
[tools-mcp.md](../../runbooks/tools-mcp.md) and
`brain/packages/orchestrator/tests/test_config_logging.py` to that binding; a sink that kept the
binding and wrote the literal in the call again is green in every suite and every scan, which the
audit-message addendum's table measured as zero rather than assumed. Two names to keep in step, and
the day the literal moves alone the documents go on being tied to the one that did not.

The shape is exactly the hole the one-name rule was built for, one word over, and the reader is
already in the right place: `logcalls.py` parses every log call's first argument to find the one
writing a message, and it already resolves a bare identifier against the module's own top level
through `moduleconstants.py`. `cortex_orchestrator/abandon.py` binds `ABANDONED_MESSAGE` and passes
it for the same reason, so the convention this would gate is already what two modules do by hand.

**What to weigh before building.** A logger name is a name and a message is a sentence, so the
generalization is not free: a module that binds some string for another purpose and happens to log
the same literal would be refused a spelling nothing is wrong with, where a `getLogger` literal
matching a binding is that binding by construction. Decide whether the rule is about any log call's
message or only about a call whose binding some document restates, and note that the second form
needs the registry to say which of its sites is a message, which is the shape
[R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md) is already weighing for
logger names. There is also a cost with a floor: `logcalls.py` stands at exactly 300 lines, so the
next rule it gains arrives with the split its own docstring draws, between which module owns a
logger name and what one call under it puts on its line.

## Trail

- 2026-08-29: opened by the close of
  [R-487](487-the-tool-audits-message-is-spelled-in-three-places-and-held-in-none.md), whose
  mutation table holds the sink's own declaration and never asks that the call passes it.
