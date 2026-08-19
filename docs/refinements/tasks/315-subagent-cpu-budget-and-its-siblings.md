# The subagent CPU budget, and the sibling asks beside it

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Opened 2026-08-19 by the close of [R-306](306-subagent-memory-budget-spelled-twice.md), which tied
the memory budget in `docker/docker-compose.subagents.yml` to the brain's own default and left the
four knobs beside it untied. They are not one job: one is the same shape as the closed entry and
costs a registry entry, and the other three need a decision before anything can be tied at all.

**The CPU budget is the same shape and cheaper.** `cpu_budget: float = Field(default=4.0, gt=0)` in
`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py` is spelled three more
times in that one compose file: the environment passthrough
`CORTEX_SUBAGENTS_CPU_BUDGET: "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"`, the container's own
`cpus: "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"`, and the comment above that limit claiming the two
are twins (`CPU_BUDGET 4.0, MEM_BUDGET_GB 8.0`). Every one of them writes `4.0`, docker's `cpus`
taking a float where its `mem_limit` will not, so this needs no second spelling and no new
machinery: promote the default to a module constant beside `DEFAULT_MEM_BUDGET_GB`, add one
`Constant` to `scripts/seamcouplings.py`, and prove it fails by drifting each place. The failure it
would catch is the memory one's twin: a container given more or fewer cores than the scheduler is
admitting against, with nothing saying so.

**The three per-subagent asks need a decision first, and one of them disagrees on purpose.**
`CORTEX_SUBAGENTS_CPUS` ships `2.0` against the field's `2.0` and `CORTEX_SUBAGENTS_VRAM_GB` ships
`3.5` against the field's `3.5`, so both could be tied as equalities today. `CORTEX_SUBAGENTS_MEMORY_GB`
ships `3.0` against the field's `2.0`, and the divergence is deliberate: the compose comment
records the measured pick (about 2.5 GiB RSS on CPU, rounded up to a 3.0 ask so two are admitted
under the memory budget) while the field default stays the GPU-less-safe placeholder. An equality
entry over that pair would redden a difference somebody chose. So closing this half means deciding
which number the field should carry, and either moving it and tying the pair or recording that the
two are independent and leaving them untied on purpose. Tying `cpus` and `vram_gb` while their
neighbour stays untied for an unwritten reason is the worst of the three outcomes.

Verify all of the above against the tree before acting on it: these are readings taken on the day
this was filed, and the numbers are exactly the kind that move.

The wider survey stays unasked here as it was there. Around fifty `${CORTEX_*:-default}`
substitutions live under `docker/` and most name a path, a model file or a host-shaped number no
Python constant declares. This entry is the four knobs measured to restate a Python default in the
one file the closed entry already touched.

## Trail

- 2026-08-19: opened by the close of [R-306](306-subagent-memory-budget-spelled-twice.md), which
  built the second spelling these knobs mostly do not need and tied the one that did.
