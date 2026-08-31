# The spill line a runbook describes and never prints

**Status:** landed 2026-08-30
**Area:** docs
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Opened 2026-08-30 by the close of
[R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), which
removed the reason these lines could not be printed.

`brain/packages/core/src/cortex_core/brain_phase.py` binds three log messages and hands each to its
own call: the warning an operator reads when the deep tier decoded below the rate its deployment
measured, and the two readings beside it. The comment above the first sends a reader to
[model-swap.md](../../runbooks/model-swap.md), and that runbook prints no rendered sample of any of
them. `brain/packages/tools/src/cortex_tools/audit.py` and
`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py` are in the same position, five
lines in three modules between them.

Until this morning a runbook could not have printed one: `logcalls.logged` matched a call whose
first argument was a literal, so a correct sample of any of these lines failed
`check-samplecheck` as a message no module logs, which is a gate failing on a true statement. That is
fixed, and the sample gate is found rather than registered, so a fenced sample added to a runbook is
held to its call site the moment it is written, level, logger, message and fields in printed order.

**What to weigh.** Not every one of the five needs printing. The tool audit's line builds its
`extra=` across statements and by condition, so `logcalls.py` does not read a field list off it
and any fenced sample of it fails as a call the reader cannot account for, which the constant
registry already says in as many words. The abandonment warning and the spill trio each write a
literal `extra=` at the call and would be held. The question for each is whether an operator
arriving at that line is helped by seeing it rendered, which is the standard the four samples
already in `docs/runbooks/` were written to.

## Trail

- 2026-08-30: opened by the close of
  [R-503](503-a-declared-log-message-is-held-to-its-call-by-one-hand-named-assertion.md), whose
  mutation table measures a runbook sample of one of these lines failing before that close and
  passing after.
- 2026-08-30: **landed** as one sample, and the entry was wrong about its own subject (ADR-0009
  quotable-line addendum). It says the spill trio writes a literal `extra=` at the call and would
  be held; two thirds of the trio do not, `_report_cadence` building one `extra` above both
  number-carrying lines and handing it over, unioned with `{"shortfall": ...}` for the warning and
  bare for the reading. `logcalls._keys` raises on both with `extra= is not a mapping written out at
  the call`, exactly as it does on the tool audit's, so the line this entry is named after is the
  one line of the five still not quotable and three of the five are out rather than one. Of the two
  that remain, the abandonment warning is described by no runbook, so printing it would mean
  writing the passage around it first; the no-reading INFO is described in the swap runbook's spill
  watch and is the one an operator is likeliest to read as a pass, so that is the one printed, and
  it earns the space by showing what the prose cannot, three work identities and no numbers at all.
  Correcting the bullets beside it found the drift a sample exists to prevent: six field names in
  an order the formatter does not print, `model`, `session_id` and `turn_id` missing outright, and
  "the same numbers" claimed for a line that differs by one field. Rewriting the calls to make them
  quotable was weighed and declined; the residue is the reader's, and it is
  [R-516](516-a-field-list-composed-above-its-call-cannot-be-quoted.md).
