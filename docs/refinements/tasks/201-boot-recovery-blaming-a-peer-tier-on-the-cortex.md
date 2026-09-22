# Boot recovery blaming a peer tier on the cortex

**Status:** done 2026-08-09
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

`converge_residency` started every `evict_models` tier inside the same `try` that decides whether
the cortex was seen serving, so one peer that would not start made the whole convergence answer
`False`, the composition root published `RESIDENCY_BOOT_FAILED`, and the overlay went amber with
"the usual assistant did not come up at startup" over a cortex that was serving turns.

Fixed on 2026-08-09, recorded at [ADR-0054 decision 2](../../adr/ADR-0030-brain-handoff.md).
`converge_residency` now answers about the cortex and nothing else: each `evict_models` peer is
cleared and restarted best effort through the swap back's own `restart_evicted`, so a `status` or a
`start` the host refuses is recorded in the manager's `BaselineTiers` and skipped.

The stated blocker was real to the line: `residency.py` stood at 299 of 300 and both call sites
reach the record through it. The split was taken by responsibility rather than by count:
`ResidencyBoard` (`residency_board.py`) now owns the bookkeeping the moves and the restore both
write into, leaving the manager the rules for when the GPU may be reassigned and who may lease it.
No public import path moved.

A run against a real sidecar showed the entry named the wrong call. The reachable misconfiguration
is a tier named in `CORTEX_SWAP_EVICT_MODELS` that the daemon has no artifact for, and such a tier
is not in its roster at all: it answers 404 to the `status` of the clearing loop, several calls
before the `start`. Witnessed live against the real `model-host` image over real HTTP, which
answered `settled=False` with an empty record while `GET /models/cortex` on the same daemon read
`ready`, and answered `settled=True` with `missing=('subagent-gpu',)` once the clearing loop
tolerated a peer failure too.

`TIERS_MISSING_DETAIL` also had to stop naming a cause. It said a tier "did not come back after a
deep task", which is false on a brain that has never escalated, so it now reads `the model host is
not running {models}, so delegated work is running on the CPU`.

## History

- 2026-08-09: Opened by the tier-outage close, which refuses that conflation everywhere else and
  left this one site alone.
- 2026-08-09: Closed hours later and ahead of its trigger. One entry opened in its place, the deep
  tier's own clearing.
