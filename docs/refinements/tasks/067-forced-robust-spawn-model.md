# The injection-resistant model forced on untrusted-content spawns

**Status:** done 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0017](../../adr/ADR-0017-subagent-model-safety.md)

A caller's choice of model is a hint rather than a decision. `SubagentRoster.resolve`, in the pure
core at the runner, reads the stored `SubagentTask.model` and `tainted` and forces the
injection-resistant default whenever the spawn can contain untrusted content, meaning a tainted
turn or a subagent with tools. A weaker model is therefore reachable only for a tool-less subagent
on an untainted turn. It is deterministic and covered over the full matrix and end to end, from
taint ledger to dispatcher stamp to task record to resolution. The mechanics are in
[ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md).

## History

- 2026-07-03: Shipped.
