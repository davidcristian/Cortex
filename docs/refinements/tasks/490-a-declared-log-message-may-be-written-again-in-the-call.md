# A declared log message may be written again in the call that logs it

**Status:** done 2026-08-30
**Area:** repo-checks
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

A module may no longer write one logger name twice, which is the rule
[R-488](488-a-declared-logger-name-is-never-held-to-the-call-that-passes-it.md) closed. Nothing said
the same about a message. `brain/packages/tools/src/cortex_tools/audit.py` binds `_MESSAGE` and
hands it to `_logger.info`, and the constant registry compares
[tools-mcp.md](../../runbooks/tools-mcp.md) and
`brain/packages/orchestrator/tests/test_config_logging.py` with that binding; a sink that kept the
binding and wrote the literal in the call again passed every suite and every scan, which a mutation
measured as zero rather than assumed.

`logcalls.py` is already in the right place: it parses every log call's first argument and resolves
a bare identifier against the module's own top level through `moduleconstants.py`.
`cortex_orchestrator/abandon.py` binds `ABANDONED_MESSAGE` and passes it for the same reason, so two
modules already follow this convention by hand. The generalization is not free: a logger name is a
name and a message is a sentence, so a module that binds some string for another purpose and happens
to log the same literal would fail over nothing wrong.

## History

- 2026-08-29: opened by the close of
  [R-487](487-the-tool-audits-message-is-written-in-three-places.md), whose
  mutation table covers the sink's own declaration and never asks that the call passes it.
- 2026-08-29: weighed by the close of
  [R-489](489-a-declared-logger-name-and-a-different-name-in-the-call.md) and left open, being a
  different question answered by a different mechanism. Two facts from that close are worth having
  here. The harm is narrower on this sink: `brain/packages/tools/tests/test_audit.py` asserts four
  whole rendered lines, so a literal that moved alone is four failures in that package, and the
  close registered the word those assertions write. And `logcalls.py` still stands at exactly 300
  lines, so the rule still arrives with a split.
- 2026-08-30: closed as a rule in `scripts/logcalls.py`, worked together with
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), which
  supplied the reading that made it affordable (ADR-0045 decision 8). The question is answered any
  log call's message, and the warning beside it was about the wrong thing: the domain is a call and
  never a binding, so a literal has to be the message of a log call before the module's own top
  level is consulted for the same string, and a module that binds a refusal for a model to read and
  logs something else is never in it. Measured before building: the brain writes 90 literal log
  messages today and not one of them is also bound at its module's top level, so the rule fails on
  nothing that exists. The narrow domain this entry offered, a binding some document restates, was
  set aside for the reason it suspected: it needs the registry to say which of its sites is a
  message, and the brain's twenty message-shaped constants, most of them model-facing refusals, show
  why nothing here can. The rule runs over the tree rather than over the modules a sample names,
  `logcalls.messages` walking every package's `src/` and `samplecheck.py` calling it beside the
  loggers. The 300-line limit was real: the split arrived with the rule, `loggernames.py` taking
  which module owns a logger name. What is still unchecked is a call using a different word from the
  one its module declares, which is
  [R-504](504-a-declared-message-and-a-different-word-in-the-call.md).
