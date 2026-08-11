# A hard budget wall

**Status:** landed 2026-07-16
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read:
"The CPU/RAM budget bounds only what the scheduler *admits* (soft, admission-only, a deliberate
tradeoff per ADR-0012 risks); hard enforcement remains a refinement behind the same
`SubagentScheduler` port." Two corrections. **That reading is impossible behind that port:** hard
enforcement over processes the scheduler never admitted is a cgroup/`.wslconfig` capability the
user's ADR-0012 constraint rules out, and a port that only sees admissions cannot supply it.
**At ADR-0012 decision 4's own reading** (refuse instead of queue) a wall already existed: a
charge larger than the whole budget raised rather than waiting forever. Its *boundary behaviour*
was the defect. The bare `ValueError` escaped `SubagentRunner.run`, `SpawnSubagentsTool`'s
`gather` (discarding every sibling's answer), and `ToolDispatcher`, which catches only
`ToolError`, reaching `converse.py`'s broad turn handler, which failed the turn with
`ERROR_CODE_INTERNAL` and left the whole `Converse` stream refusing further turns; and
`SubagentsConfig` never checked an ask against the budget, so env alone could reach that state.
What landed: the typed `SubagentAdmissionError` on the port, caught by the runner and
degraded to an `ok=False` "refused before running" `SubagentResult`, plus a boot-time config
check that no roster entry asks more than the whole budget. A transient full budget still
**queues**, deliberately: the work runs seconds later, depth-1 drains the queue, and a waiting
spawn holds none of the budget, so refusing it saves nothing. Also noted: with respect to what it
charges the budget was already hard; "soft" only ever meant that it binds nothing it did not
admit. Behind it, two new entries below.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as one half of a two-part
  entry.
- 2026-07-16: Closed on the finding that the wall existed and now refuses as a value, recorded at
  the [ADR-0012 admission-wall addendum](../../adr/ADR-0012-resource-governance.md). The wall was being
  delivered as a turn-killing exception; making it refuse as a value, and refusing the
  misconfiguration at boot, opened the two entries behind it, a bounded admission wait and a read
  timeout on the subagent HTTP client, which name the waits nothing bounded.
- 2026-08-09: Both of the entries it opened landed, hours apart and in that dependency order.
