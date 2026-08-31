# The subagent CPU budget, and the sibling asks beside it

**Status:** landed 2026-08-20
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
`3.5` against the field's `3.5`, so both could be tied as equalities today.
`CORTEX_SUBAGENTS_MEMORY_GB` ships `3.0` against the field's `2.0`, and the divergence is
deliberate: the compose comment records the measured pick (about 2.5 GiB RSS on CPU, rounded up to a
3.0 ask so two are admitted under the memory budget) while the field default stays the GPU-less-safe
placeholder. An equality entry over that pair would fail on a difference somebody chose. So closing
this half means deciding which number the field should carry, and either moving it and tying the
pair or recording that the two are independent and leaving them untied on purpose. Tying `cpus` and
`vram_gb` while their neighbour stays untied for an unwritten reason is the worst of the three
outcomes.

Verify all of the above against the tree before acting on it: these are readings taken on the day
this was filed, and the numbers are exactly the kind that move.

The wider survey stays unasked here as it was there. Around fifty `${CORTEX_*:-default}`
substitutions live under `docker/` and most name a path, a model file or a host-shaped number no
Python constant declares. This entry is the four knobs measured to restate a Python default in the
one file the closed entry already touched.

## Trail

- 2026-08-19: opened by the close of [R-306](306-subagent-memory-budget-spelled-twice.md), which
  built the second spelling these knobs mostly do not need and tied the one that did.
- 2026-08-20: landed as four registry entries, and the half that needed a decision got one. The CPU
  budget went in as this entry framed it, a module constant plus three spends in the one compose
  file, and it needed no second spelling: docker's `cpus` takes a float, so all three write the
  digits the field declares, and the passthrough and the cgroup cap are pinned as a counted pair
  because they are the twinning the comment beside them claims. Of the three asks, `cpus` and
  `vram_gb` were tied as they stood, and `memory_gb` moved: the field takes the measured `3.0` the
  stack has shipped all along, since a default of `2.0` under-charges every spawn by half a gigabyte
  and admits onto room the container's own cap would refuse, which is the same unsafe direction the
  VRAM ask was corrected for and the reason that pair is one number today. Nothing moves for a
  deployment running the shipped compose file. The registry outgrew its file in the process and
  split a third time, into `scripts/shippedcouplings.py`, along the line `seamcouplings.py` had been
  describing in its own second paragraph. Twelve drifts were planted on the real tree and reverted,
  each failing its own entry and no other. The reasoning is the ADR-0012 addendum on these four
  knobs; the split is recorded at ADR-0029 beside the two before it. The wider survey this entry
  declined to ask, and the memory budget's close declined before it, finally has a file of its own
  ([R-333](333-compose-defaults-that-restate-a-declaration.md)).
