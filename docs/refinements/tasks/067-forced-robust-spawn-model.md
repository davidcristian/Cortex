# Forced-robust model on untrusted-content spawns

**Status:** landed 2026-07-03
**Area:** untrusted-content
**Origin:** [ADR-0017](../../adr/ADR-0017-subagent-model-safety.md)

The mechanics are in [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md).
The choice is an optimization *hint, not
authority*: `SubagentRoster.resolve` (pure core, at the runner, over the store-carried
`SubagentTask.model`/`tainted`) forces the injection-robust default whenever the spawn path can
carry untrusted content (tainted turn or tools-enabled subagent), so a weak model is reachable
only for a tool-less subagent on an untainted turn. Deterministic, CI-proven over the full
matrix and end to end (taint ledger → dispatcher stamp → task record → resolution).

## Trail

- 2026-07-03: Landed with Slice 8.6.
