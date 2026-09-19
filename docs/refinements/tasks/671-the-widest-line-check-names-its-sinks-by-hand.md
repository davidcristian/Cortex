# The widest-line check names its sinks by hand

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-19

Opened 2026-09-15 by the close of
[R-337](337-a-bounded-value-leaves-the-line-unbounded.md), which held the widest line each shipped
sink builds under the log driver's cliff and left the set of sinks a written list.

`test_widest_line.py` has one case per sink and both cases are hand-written: one names
`LoggingAuditSink` and its eleven keys, the other `LoggingRecallSink` and its eleven. A sink that
lands in the brain tomorrow is held by neither, and nothing says so. The same shape is what
`flagcheck.py` refused to accept on the subagent servers, where the set a rule runs over is derived
from the stack's own wiring rather than read from a list, so a server added anywhere is covered the
day it is written (ADR-0029 addendum on deriving the set a rule runs over).

**Why it was left.** Two sinks, both old, and a third is a change somebody is making deliberately
rather than something that appears. The cost of the miss is one unmeasured line rather than a wrong
answer: the check that exists does not become false when a sink is added, it just stops being
complete.

**What fired.** The third sink landed on 2026-09-17: `JsonLinesAuditSink` in
`brain/packages/tools/src/cortex_tools/audit_file.py`, wired with `TeeAuditSink` by
`tool_audit_from_config` in `dispatch_builders.py` when `CORTEX_TOOLS_AUDIT_FILE` is set. Its record
goes to a file, which has no driver cliff, but a failed append writes a log line of its own,
`tool.audit.gap`, carrying `path`, `tool` and `error`, and `tool` is the model's. No case in
`test_widest_line.py` drives it and nothing said so, which is this entry's defect happening once.
The old trigger's reading, `grep -rn "Logging.*Sink"`, could not have shown it: it matched a class
name prefix the new sink does not carry. The gap line itself cannot reach the cliff. It carries three
fields, and `log_fields.py` measures seven cut fields at 14,536 characters. `TeeAuditSink` writes
no line of its own. So what fired is the completeness the entry is about, not a line past the cliff.

The same landing made the suite's docstring and the ADR-0038 widest-line addendum wrong in a
detail: `schedule_builders` and `subagent_builders` no longer construct `LoggingAuditSink` but spend
the `setup.audit` that `dispatch_builders` builds, so the concrete sink classes are named in two
orchestrator modules, `dispatch_builders.py` and `memory_builders.py`.

**The fix, brain-side.** In `brain/packages/orchestrator/tests/test_widest_line.py`:

1. Derive the wired set by reading the orchestrator's source with `ast`: every name ending in `Sink`
   that a module under `brain/packages/orchestrator/src/cortex_orchestrator/` imports from
   `cortex_tools` or `cortex_memory`. Today that is `JsonLinesAuditSink`, `LoggingAuditSink`,
   `TeeAuditSink` and `LoggingRecallSink`.
2. Add a case for `JsonLinesAuditSink`'s gap line: point the sink at a directory so the append
   raises `IsADirectoryError`, record an invocation whose `tool` is past `VALUE_CHARS`, and assert
   the line stays under `ONE_DOCKER_MESSAGE`, carries one cut marker and the keys `path`, `tool`
   and `error`.
3. Keep an exemption map naming each sink that writes no line, with its reason, today only
   `TeeAuditSink`. Assert that the derived set equals the sinks with a case plus the exempted ones,
   and that every exemption is still in the derived set, so a stale one fails as it does in
   `settingscheck.py`.
4. Correct the docstring's list of builders to the two that name a sink class.

The judgement a derivation cannot supply, which of a sink's fields a caller fills, stays in each
case, and a new sink fails the set assertion until somebody writes that case or that exemption.

## Trail

- 2026-09-19: trigger fired, by the tool audit file sink of 2026-09-17, and the entry moved to
  actionable with the fix above. The trigger is removed because an actionable entry carries none.
  Recorded in the ADR-0038 trigger-sweep addendum of the same day.
