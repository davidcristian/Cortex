# Placement-aware CPU charging

**Status:** declined 2026-07-16
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`admit` charges every spawn its full `cpus` and `memory_gb` regardless of placement. Charging
GPU-placed subagents less was called a tweak behind the same port, and it is not: `admit(request)`
takes a `PlacementRequest`, which has no placement, and `SubagentRunner.run` enters admission before
it places, by ADR-0012 decision 5, so the charge cannot know the target. Making it placement-aware
needs a port change or the admit-then-place inversion decision 5 exists to prevent, where a
GPU-placed spawn queuing for a CPU slot holds reserved VRAM while it waits.

The discount would also buy nothing. Each roster entry holds one `LlamaCppBackend` per target and a
backend holds its model lease for the whole stream, so same-entry spawns overlap at most two ways
whatever the budget admits. Measured live on the Qwen-2B override: two concurrent spawns took 4.8 s
through two backend objects and 10.0 s through one.

It reopens with a second GPU-capable executor, so that two GPU-placed spawns can run at once and a
placement-aware charge changes how many are admitted. That is a port change, not a tweak.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section as one half of a two-part
  entry.
- 2026-07-16: Declined, on a wrong premise and no gain, recorded at
  [ADR-0012 decision 9](../../adr/ADR-0012-resource-governance.md). The two-part entry it belonged
  to closed as two different outcomes.
- 2026-07-18: The GPU-placed runtime arrived and did not reopen it, since one hosted GPU tier is
  still one `LlamaCppBackend` per target per roster entry.
- 2026-08-08: One of its sentences went false and the conclusion did not. The subagent request was
  measured at 3.5 GiB against 5.4 GiB of headroom, so a spawn really is GPU-placed and "there is
  nothing to discount today" no longer describes the shipped stack. The headroom holds one GPU spawn
  anyway.
- 2026-08-09: The same measurement corrected the reading from plain serialization to a limit of two
  lock objects, when the admission bound's arithmetic was corrected against it.
