# A cost-aware batch cap

**Status:** declined 2026-08-18
**Area:** tools-mcp
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

Recorded inside [R-045](045-spawn-subagents-batch-cap.md): a batch cap counted in placements or
estimated VRAM rather than in items, if roster entries ever differ enough that eight of one is not
eight of another. Declined, because neither unit bounds the right thing.

**A cap in placements is the cap in items under another name.**
`SpawnSubagentsTool.invoke` builds exactly one `SubagentTask` per `instructions` entry
([spawn.py](../../../brain/packages/core/src/cortex_core/spawn.py)), and the runner calls
`placer.place` exactly once per task
([runner.py](../../../brain/packages/core/src/cortex_core/runner.py)). The only second attempt is
the sequential re-run of a GPU placement that did not answer, and it releases the first
reservation in a `finally` before it runs, reusing the same admission, so it is never a concurrent
placement.

**Estimated VRAM is already bounded, by something a batch size cannot breach.**
`VramBudgetPlacer.place` ([placer.py](../../../brain/packages/core/src/cortex_core/placer.py))
fit-tests each spawn against the headroom left by the soft cap, the resident model and what is
already placed, and moves it to CPU when it does not fit rather than refusing. A batch of eight
can therefore never exceed the VRAM budget however much it asks for, so a VRAM-denominated cap
would bound a resource that is already hard-bounded, and would not bound the one the cap exists
for, which is how many inferences the turn sits through.

**The bound has to be statable before the batch is composed.** The cap ships twice on purpose, as
`maxItems` that a constrained decoder can enforce and as prose for a model that reads only
descriptions ([spawn_spec.py](../../../brain/packages/core/src/cortex_core/spawn_spec.py)). A
summed-cost cap is enforceable by neither, and the refusal would depend on which models the cortex
happened to pick, so the model could no longer restate the rule it must obey. It also reverses an
argued property: the oversized array is refused before the items are parsed, while a cost-aware
cap must parse every item's model first.

**And the trigger is measurably unmet.** The one shipped alternate roster entry asks `cpus: 2.0`,
identical to the default, with a smaller memory request that never binds
([docker-compose.subagents-roster.yml](../../../docker/docker-compose.subagents-roster.yml)
against [docker-compose.subagents.yml](../../../docker/docker-compose.subagents.yml)). Admission
is CPU-bound for both, two at a time under the shipped budget, so eight of one is eight of another
where it counts. The only figure that differs and reaches the placer is a VRAM number the roster
file itself documents as unmeasured, that entry having no GPU executor at all. What would reopen
the question is a roster entry whose `cpus` differs, because that is the one field that changes
how many of a batch run at once, and the answer there is a per-entry ceiling rather than a
cost-denominated cap.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired. This is one of
  the entries whose trigger is a deployment doing something rather than a file saying something.
- 2026-08-18: Declined on a reading of the tree. The finding worth keeping is that placements and
  items are the same count in this wiring, which makes half of the proposal a rename; the other
  half bounds a resource the placer already moves to CPU rather than overspending. The sibling
  [R-046](046-a-cortex-subagents-max-batch-setting.md) is a separate question, about the cap's value rather
  than its unit. Both readings are ADR-0010 decisions 11 and 12.
