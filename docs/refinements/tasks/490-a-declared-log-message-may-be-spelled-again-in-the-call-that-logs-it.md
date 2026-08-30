# A declared log message may be spelled again in the call that logs it

**Status:** landed 2026-08-30
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
- 2026-08-29: weighed by the close of
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md) and **left open**, being
  a different question answered by a different mechanism. That close is about a declaration and the
  call handed it, which is held by places outside the module and was closed by registering them;
  this one is about one module spelling the same word twice, which no far side can see and which
  only a rule in `logcalls.py` reaches. Two facts from that close are worth having here. The
  harm named above is now narrower on this sink: `brain/packages/tools/tests/test_audit.py` asserts
  four whole rendered lines, so a literal that moved alone is four reds in that package, and the
  close registered the word those assertions spell, so they can no longer be deleted quietly. And
  the floor this entry named is unchanged: `logcalls.py` still stands at exactly 300 lines, so the
  rule still arrives with the split its own docstring draws.
- 2026-08-30: **landed** as a rule in `scripts/logcalls.py`, worked together with
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), which
  supplied the reading that made it affordable (ADR-0009 handed-message addendum). The question
  this entry named is answered **any log call's message**, and the warning beside it turned out to
  be about the wrong thing: the domain is a call and never a binding, so a literal has to be the
  message of a log call before the module's own top level is consulted for the same string, and a
  module that binds a refusal for a model to read and logs something else is never in it. Measured
  before building: the brain writes 90 literal log messages today and not one of them is also bound
  at its module's top level, so the rule refuses nothing that exists. The narrow domain this entry
  offered as the alternative, a binding some document restates, was set aside for the reason it
  suspected: it needs the registry to say which of its sites is a message, and the section of that
  addendum on the brain's twenty message-shaped constants shows why nothing here can. The rule runs
  over the tree rather than over the modules a sample names, `logcalls.messages` walking every
  package's `src/` and `samplecheck.py` calling it beside the loggers. The floor this entry
  predicted was real: `logcalls.py` stood at exactly 300 lines and the split landed with the rule,
  along the seam its own docstring drew, `loggernames.py` taking which module owns a logger name.
  What is still not held is a call carrying a DIFFERENT word from the one its module declares, which
  is [R-504](504-a-declared-message-and-a-different-word-in-the-call.md).
