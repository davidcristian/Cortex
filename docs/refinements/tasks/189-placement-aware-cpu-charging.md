# Placement-aware CPU charging

**Status:** declined 2026-07-16
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read:
"`admit` charges every spawn its full `cpus`/`memory_gb` regardless of placement (conservative);
charging GPU-placed subagents less is a tweak behind the same port." It is not behind that port.
`admit(request)` takes a `PlacementRequest`, which carries no placement, and `SubagentRunner.run`
enters admission *before* it places, by ADR-0012 decision 5, so the charge cannot know the target.
Making it placement-aware needs a port change (a target argument, or an `admit` yielding a
re-chargeable handle) or the admit/place inversion decision 5 exists to prevent, where a
GPU-placed spawn queuing for a CPU slot holds reserved VRAM while it waits. The discount would
also buy nothing: each roster entry holds one `LlamaCppBackend` per target and a backend holds its
model lease for the whole stream, so same-entry spawns serialize there whatever the budget admits
(measured live on the Qwen-2B override: two concurrent spawns took 4.8 s through two backend
objects, 10.0 s through one, a ratio of 2.08). And there is nothing to discount today, since
`CORTEX_SUBAGENTS_VRAM_GB=5.5` sits deliberately above the GPU headroom, so every spawn overflows
to CPU. **Reopens** with a second GPU-capable executor, as a port change rather than a tweak.
**The GPU-placed runtime arrived on 2026-07-18 and did not reopen it**, which is worth stating
because this entry used to name that runtime as the condition. One hosted GPU subagent tier is
still one `LlamaCppBackend` per target per roster entry, so the measured serialization above is
unchanged and the discount would still buy nothing; and the shipped `CORTEX_SUBAGENTS_VRAM_GB=5.5`
still sits above the headroom, so there is still nothing to discount. What would reopen it is what
ADR-0030 decision 8's addendum already says: a **second** GPU-capable executor, so that two
GPU-placed spawns can actually run at once and a placement-aware charge changes how many are
admitted.
**One sentence above went false on 2026-08-08 and the conclusion did not.** The ask was measured
and is now 3.5 GiB against 5.4 GiB of headroom, so a spawn really is GPU-placed and "there is
nothing to discount today" no longer describes the shipped stack. What still declines the entry is
the other half, which the measurement did not touch: one `LlamaCppBackend` per target per roster
entry caps same-entry overlap at two lock objects whatever the budget admits, and the headroom
holds one GPU spawn anyway, so a discount would change nothing about how many run. (That cap
read as plain serialization until 2026-08-09, when the admission bound's arithmetic was corrected
against this same measurement.)

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as one half of a two-part
  entry.
- 2026-07-16: Closed as declined, wrong premise and no gain, recorded at the
  [ADR-0012 admission-wall addendum](../../adr/ADR-0012-resource-governance.md). The two-part entry it
  belonged to closed as two different outcomes, which is why an entry naming two things should be
  read as two.
- 2026-07-18: The GPU-placed runtime arrived and did not reopen it, one hosted GPU tier still being
  one `LlamaCppBackend` per target per roster entry, so the condition became the one ADR-0030
  decision 8's addendum gives it, a second GPU-capable executor.
- 2026-08-08: One of its sentences went false and the conclusion did not. The subagent ask was
  measured at 3.5 GiB against 5.4 GiB of headroom, so a spawn really is GPU-placed and "there is
  nothing to discount today" no longer describes the shipped stack.
- 2026-08-09: The same measurement corrected the entry's serialization reading, from plain
  serialization to a cap of two lock objects, when the admission bound's arithmetic was corrected
  against it.
