# The spill line a runbook describes and never prints

**Status:** done 2026-08-30
**Area:** docs
**Origin:** [ADR-0045](../../adr/ADR-0045-documented-log-lines.md)

`brain/packages/core/src/cortex_core/brain_phase.py` binds three log messages and hands each to its
own call: the warning an operator reads when the deep tier decoded below the rate its deployment
measured, and the two readings beside it. The comment above the first sends a reader to
[model-swap.md](../../runbooks/model-swap.md), and that runbook prints no rendered sample of any of
them. `brain/packages/tools/src/cortex_tools/audit.py` and
`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py` are in the same position, five
lines in three modules between them.

Until 2026-08-30 a runbook could not have printed one: `logcalls.logged` matched a call whose first
argument was a literal, so a correct sample of any of these lines failed `check-samplecheck` as a
message no module logs. That is fixed, and `samplecheck.py` finds the call rather than reading a
list, so a fenced sample added to a runbook is compared with its call site the moment it is written,
on level, logger, message and fields in printed order.

## History

- 2026-08-30: opened by the close of
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), whose
  mutation table measures a runbook sample of one of these lines failing before that close and
  passing after.
- 2026-08-30: closed as one sample, and the entry was wrong about its own subject (ADR-0045 decision
  10). It said the spill trio writes a literal `extra=` at the call and could be checked; two thirds
  of the trio do not, `_report_cadence` building one `extra` above both lines that report a number and
  handing it over, combined with `{"shortfall": ...}` for the warning and bare for the reading.
  `logcalls._keys` raises on both with `extra= is not a mapping written out at the call`, exactly as
  it does on the tool audit's, so the line this entry is named after is the one line of the five
  still not quotable and three of the five are out rather than one. Of the two that remain, the
  abandonment warning is described by no runbook, so printing it would mean writing the passage
  around it first; the no-reading INFO is described in the swap runbook's spill watch and is the one
  an operator is likeliest to read as a pass, so that is the one printed, and it is worth the space
  because it shows what the prose cannot, three work identities and no numbers at all. Correcting
  the bullets beside it found the disagreement a sample exists to prevent: six field names in an
  order the formatter does not print, `model`, `session_id` and `turn_id` missing outright, and the
  same numbers claimed for a line that differs by one field. Rewriting the calls to make them
  quotable was weighed and declined; the residue is
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md).
