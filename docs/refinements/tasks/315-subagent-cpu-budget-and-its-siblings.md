# The subagent CPU budget, and the three per-subagent settings beside it

**Status:** done 2026-08-20
**Area:** repo-checks
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

[R-306](306-a-subagent-memory-budget-default-written-three-times.md) registered the memory budget in
`docker/docker-compose.subagents.yml` against the brain's own default and left the four settings
beside it unchecked. They are not one job: one is the same case as the closed entry and costs a
registry entry, and the other three need a decision first.

The CPU budget is the same case and cheaper. `cpu_budget: float = Field(default=4.0, gt=0)` in
`brain/packages/orchestrator/src/cortex_orchestrator/config_subagents.py` is written three more
times in that one compose file: the environment passthrough
`CORTEX_SUBAGENTS_CPU_BUDGET: "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"`, the container's own
`cpus: "${CORTEX_SUBAGENTS_CPU_BUDGET:-4.0}"`, and the comment above that limit saying the two
match (`CPU_BUDGET 4.0, MEM_BUDGET_GB 8.0`). All of them write `4.0`, docker's `cpus` taking a
float where its `mem_limit` will not, so this needs no second form: move the default to a module
constant beside `DEFAULT_MEM_BUDGET_GB` and add one `Constant` to `scripts/wirecouplings.py`. The
failure it catches is the memory one's twin, a container given more or fewer cores than the
scheduler admits against.

The three per-subagent settings need a decision first, and one differs deliberately.
`CORTEX_SUBAGENTS_CPUS` ships `2.0` against the field's `2.0` and `CORTEX_SUBAGENTS_VRAM_GB` ships
`3.5` against the field's `3.5`, so both could be registered as equalities today.
`CORTEX_SUBAGENTS_MEMORY_GB` ships `3.0` against the field's `2.0`: the compose comment records the
measured choice (about 2.5 GiB RSS on CPU, rounded up to 3.0 so two fit under the memory budget)
while the field default stays the placeholder that is safe without a GPU. An equality entry over
that pair would fail on a difference somebody chose, so closing this half means deciding which
number the field should have, then either moving it and registering the pair or recording that the
two are independent.

The wider survey of about fifty `${CORTEX_*:-default}` substitutions under `docker/` stays unasked
here, as it did in the entry before this one.

## History

- 2026-08-19: Opened by the close of [R-306](306-a-subagent-memory-budget-default-written-three-times.md), which
  built the second value form these settings mostly do not need.
- 2026-08-20: Fixed as four registry entries, and the half that needed a decision got one. The CPU
  budget went in as described, a module constant plus three uses in the one compose file, and
  needed no second form: docker's `cpus` takes a float, so all three write the digits the field
  declares, and the passthrough and the cgroup cap are registered as a counted pair because they
  are the match the comment beside them claims. Of the three per-subagent settings, `cpus` and
  `vram_gb` were registered as they stood, and `memory_gb` moved: the field takes the measured
  `3.0` the stack has shipped all along, since a default of `2.0` under-charges every spawn by half
  a gigabyte and admits onto room the container's own cap would refuse, the same unsafe direction
  the VRAM value was corrected for. Nothing changes for a deployment running the shipped compose
  file. The registry passed the line cap again and split a third time, into
  `scripts/shippedcouplings.py`. Twelve differences were planted on the real tree and reverted,
  each failing its own entry and no other. The reasoning is ADR-0012 decision 14; the split is
  recorded at ADR-0029 beside the two before it. The wider survey this entry declined to ask now
  has a file of its own ([R-333](333-compose-defaults-that-restate-a-declaration.md)).
