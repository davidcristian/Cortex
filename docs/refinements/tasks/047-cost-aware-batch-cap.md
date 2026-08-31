# A cost-aware batch cap

**Status:** declined 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

Recorded inside the entry for the batch cap on `spawn_subagents`, in the list of items remaining
behind the same tool:

> a **cost-aware batch** (a cap in placements or estimated VRAM rather than in items) if roster
> entries ever differ enough that eight of one is not eight of another

The cap it would replace counts items: "`MAX_SPAWN_BATCH = 8` ... **refuses** an oversized batch
rather than truncating it", each subagent in a batch being "an admission slot, a placement, and an
inference".

**Declined, because neither unit it proposes bounds the right thing.** Read against the tree on
2026-08-18, both of the units it offers turn out to be the wrong bound.

**A cap in placements is the cap in items, spelled differently.** `SpawnSubagentsTool.invoke`
builds exactly one `SubagentTask` per `instructions` entry
([spawn.py](../../../brain/packages/core/src/cortex_core/spawn.py)), and the runner calls
`placer.place` exactly once per task
([runner.py](../../../brain/packages/core/src/cortex_core/runner.py)). The only second attempt is
the sequential re-run of a GPU placement that did not answer, and it releases the first
reservation in a `finally` before it runs, reusing the same admission, so it is never a concurrent
placement. Placements equal items, and renaming a bound is not changing one.

**Estimated VRAM is already bounded, and bounded by something a batch size cannot breach.**
`VramBudgetPlacer.place` ([placer.py](../../../brain/packages/core/src/cortex_core/placer.py))
fit-tests each spawn against the headroom left by the soft cap, the resident model and what is
already placed, and **spills to CPU** when it does not fit rather than refusing. A batch of eight
can therefore never exceed the VRAM budget however much it asks for, so a VRAM-denominated cap
would bound a resource that is hard-bounded already, and would not bound the one the origin
addendum says the cap exists for, which is how many inferences the turn sits through.

**The bound has to be statable before the batch is composed.** The cap ships twice on purpose, as
`maxItems` a constrained decoder can enforce structurally and as prose for a model that reads only
descriptions ([spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py)). A
summed-cost cap is enforceable by neither, and the refusal would then depend on which models the
cortex happened to pick, so the model could no longer restate the rule it must obey. It also
reverses an argued property: the oversized array is refused *ahead* of item parsing, before a
single task is stored or a subagent placed, while a cost-aware cap must parse every item's model
first.

**And the trigger is measurably unmet.** The one shipped alternate roster entry asks `cpus: 2.0`,
identical to the default, with a smaller memory ask that never binds
([docker-compose.subagents-roster.yml](../../../docker/docker-compose.subagents-roster.yml) against
[docker-compose.subagents.yml](../../../docker/docker-compose.subagents.yml)). Admission is
CPU-bound for both, two at a time under the shipped budget, so eight of one *is* eight of another
where it counts. The only figure that differs and reaches the placer is a VRAM number the roster
file itself documents as unmeasured, since that entry has no GPU executor at all. What would
reopen the question is a roster entry whose `cpus` differs, because that is the one field that
changes how many of a batch run at once, and the honest answer there is a per-entry ceiling rather
than a cost-denominated cap.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index names the salience and batch-cap knobs among the entries whose trigger is a
  deployment doing something rather than a file saying something, so no reading of the code settles
  them.
- 2026-08-18: Declined on a re-derivation of the tree rather than on that sweep. The finding worth
  keeping is that placements and items are the same count in this wiring, which is why half of the
  proposal was a rename; the other half bounds a resource the placer already spills rather than
  overspends. The sibling ceiling knob ([046](046-subagents-max-batch-knob.md)) is a separate
  question, about the cap's value rather than its unit, and was read in the same pass. Both readings
  are recorded in the origin decision's addendum.
