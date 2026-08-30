# The spill line a runbook describes and never prints

**Status:** open, actionable
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
`check-samplecheck` as a message no module logs, which is a gate refusing a true statement. That is
fixed, and the sample gate is found rather than registered, so a fenced sample added to a runbook is
held to its call site the moment it is written, level, logger, message and fields in printed order.

**What to weigh.** Not every one of the five wants printing. The tool audit's line builds its
`extra=` across statements and by condition, so `logcalls.py` refuses to read a field list off it
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
