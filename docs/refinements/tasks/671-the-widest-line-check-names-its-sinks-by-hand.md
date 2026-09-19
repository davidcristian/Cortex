# The widest-line check names its sinks by hand

**Status:** done 2026-09-19
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

`test_widest_line.py` compares the widest line each shipped sink builds against the log driver's
cliff, and it had one hand-written case per sink: one for `LoggingAuditSink` and its eleven keys,
one for `LoggingRecallSink` and its eleven. A sink added tomorrow was covered by neither, and
nothing said so. `flagcheck.py` refused that same shape on the subagent servers, where the set a
rule runs over is derived from the stack's own wiring rather than read from a list (ADR-0043).

The cost of the miss was one unmeasured line rather than a wrong answer: the check does not become
false when a sink is added, it stops being complete.

**What fired.** The third sink arrived on 2026-09-17: `JsonLinesAuditSink` in
`brain/packages/tools/src/cortex_tools/audit_file.py`, wired with `TeeAuditSink` by
`tool_audit_from_config` in `dispatch_builders.py` when `CORTEX_TOOLS_AUDIT_FILE` is set. Its record
goes to a file, which has no driver cliff, but a failed append writes a log line of its own,
`tool.audit.gap`, with `path`, `tool` and `error`, and `tool` is the model's. No case drove it and
nothing said so. The old trigger's reading, `grep -rn "Logging.*Sink"`, could not have shown it: it
matched a class name prefix the new sink does not have. The gap line itself cannot reach the cliff,
since it has three fields and `log_fields.py` measures seven cut fields at 14,536 characters, and
`TeeAuditSink` writes no line of its own. So what fired is the completeness this entry is about, not
a line past the cliff.

**What closed it.** `brain/packages/orchestrator/tests/test_widest_line.py` now derives the wired
set by reading the orchestrator's source with `ast`: every name ending in `Sink` that a module under
`brain/packages/orchestrator/src/cortex_orchestrator/` imports from `cortex_tools` or
`cortex_memory`, which today is `JsonLinesAuditSink`, `LoggingAuditSink`, `TeeAuditSink` and
`LoggingRecallSink`. It has a case for `JsonLinesAuditSink`'s gap line, driven by pointing the sink
at a directory so the append raises `IsADirectoryError` with a `tool` past `VALUE_CHARS`, asserting
the line stays under `ONE_DOCKER_MESSAGE` with one cut marker and the keys `path`, `tool` and
`error`. It keeps an exemption map naming each sink that writes no line with its reason, today only
`TeeAuditSink`, and asserts that the derived set equals the sinks with a case plus the exempted
ones, so a stale exemption fails as it does in `settingscheck.py`. The judgement a derivation cannot
supply, which of a sink's fields a caller fills, stays in each case, and a new sink fails the set
assertion until somebody writes a case or an exemption.

The same change corrected the suite's docstring: `schedule_builders` and `subagent_builders` no
longer construct `LoggingAuditSink` but use the `setup.audit` that `dispatch_builders` builds, so
the concrete sink classes are named in two orchestrator modules, `dispatch_builders.py` and
`memory_builders.py`.

## History

- 2026-09-15: opened by the close of
  [R-337](337-a-bounded-value-leaves-the-line-unbounded.md), which measured the widest line each
  shipped sink builds and left the set of sinks a written list. Two sinks, both old, and a third is
  a change somebody makes deliberately rather than something that appears.
- 2026-09-19: trigger fired, by the tool audit file sink of 2026-09-17, and the entry moved to
  actionable.
- 2026-09-19: done. The decision is
  [ADR-0051](../../adr/ADR-0051-log-line-rendering.md) decision 15.
