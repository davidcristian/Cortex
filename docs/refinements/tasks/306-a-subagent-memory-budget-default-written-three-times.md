# A subagent memory budget default written three times and checked nowhere

**Status:** done 2026-08-19
**Area:** repo-checks
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The default for `CORTEX_SUBAGENTS_MEM_BUDGET_GB` was written in three places:

- `config_subagents.py`'s typed field, `mem_budget_gb: float = Field(default=8.0, gt=0)`.
- `docker/docker-compose.subagents.yml:85`, which passes
  `CORTEX_SUBAGENTS_MEM_BUDGET_GB: "${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}"` to the brain.
- `docker/docker-compose.subagents.yml:158` and `:159`, `mem_limit:
  "${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g"` and the matching `memswap_limit`. The default has to be
  `8` there rather than `8.0`, because docker does not accept `8.0g` as a size.

Raising the field to 12 left a container capped at 8 GB while the admission scheduler went on
admitting up to 12 GB of subagents, which is the failure the resource governance work exists to
prevent, and nothing reported it. The two compose values agreed with each other only by hand, and
`crosscheck.py` had no entry for either.

The wider question, whether every compose default that repeats a Python default should be checked,
is deliberately not asked here. About fifty `${CORTEX_*:-default}` substitutions live under
`docker/`, and most name a path, a model file or a machine-specific number that no Python constant
declares. This is the one measured case of a single number written in three places, two of them in
the same file.

## History

- 2026-08-18: Opened by the close of [40](040-a-configurable-limit-for-the-salience-policy.md), whose own compose default
  was registered in the same session; this is the neighbour that survey found unchecked.
- 2026-08-19: Half the obstacle is gone and the entry stays open. The close of
  [R-308](308-crosscheck-cannot-tie-a-decimal.md) taught `values.py` to read a decimal, and it
  reduces to the digits it is written with, so `8.0` and `8` are two different values and the two
  container limits cannot be covered by one search text. What remains is a declaration of
  `Field(default=8.0, gt=0)` rather than a bare number.
- 2026-08-19: Fixed as one registry entry over four uses. `DEFAULT_MEM_BUDGET_GB = 8.0` is now a
  module constant in `config_subagents.py` that `mem_budget_gb` refers to, because a reducer taught
  to read `Field(...)` would be a language-independent module that knows pydantic, and three fields
  in that class already refer to module constants. `Mention.form` chooses `Form.WRITTEN` or
  `Form.WHOLE`, the whole form is computed from the declared value rather than typed beside it,
  and a non-zero fraction is refused instead of truncated. `values.form_fault` refuses any
  entry whose mentions all use the second form, since `8` and `8.0` are one whole number. Proved
  able to fail seven times on the real tree and reverted each time. The reasoning is ADR-0012
  decision 14; the value forms are in
  [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md).
  [R-315](315-subagent-cpu-budget-and-its-siblings.md) opens for the CPU budget in the same file
  and the three settings beside it, one of which differs from its field deliberately.
