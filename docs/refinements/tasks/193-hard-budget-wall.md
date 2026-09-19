# A hard budget limit

**Status:** done 2026-07-16
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The CPU and RAM budget was described as soft, bounding only what the scheduler admits, with hard
enforcement left as a refinement behind the same `SubagentScheduler` port. Two corrections.

Hard enforcement behind that port is impossible: enforcing over processes the scheduler never
admitted is a cgroup or `.wslconfig` capability the ADR-0012 constraint rules out, and a port that
only sees admissions cannot supply it.

And a limit already existed at ADR-0012 decision 4's reading: a charge larger than the whole budget
raised rather than waiting forever. The defect was what happened at that boundary. The bare
`ValueError` escaped `SubagentRunner.run`, `SpawnSubagentsTool`'s `gather` (discarding every
sibling's answer), and `ToolDispatcher`, which catches only `ToolError`, reaching `converse.py`'s
broad turn handler, which failed the turn with `ERROR_CODE_INTERNAL` and left the whole `Converse`
stream refusing further turns. `SubagentsConfig` also never checked a request against the budget, so
the environment alone could reach that state.

What shipped: the typed `SubagentAdmissionError` on the port, caught by the runner and turned into
an `ok=False` "refused before running" `SubagentResult`, plus a boot-time config check that no
roster entry asks for more than the whole budget. A transiently full budget still queues,
deliberately: the work runs seconds later, depth-1 drains the queue, and a waiting spawn holds none
of the budget.

With respect to what it charges, the budget was already hard. "Soft" only ever meant that it binds
nothing it did not admit.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section as one half of a two-part
  entry.
- 2026-07-16: Closed on the finding that the limit existed and now refuses as a value, recorded at
  [ADR-0012 decision 9](../../adr/ADR-0012-resource-governance.md). It opened two entries behind it,
  a bounded admission wait and a read timeout on the subagent HTTP client, which name the two waits
  nothing bounded.
- 2026-08-09: Both of those entries closed, hours apart and in that dependency order.
