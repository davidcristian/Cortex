# A subagent budget's default is spelled twice in one compose file and tied nowhere

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Found 2026-08-18 while registering the salience limit's compose default as a cross-tree constant,
which is what [40](040-salience-limit-knob.md) closed. Surveying what else `docker/` spells a second
time turned up one variable whose own default is written twice inside a single file, in two shapes
that cannot be made identical:

- `docker/docker-compose.subagents.yml:85` passes `CORTEX_SUBAGENTS_MEM_BUDGET_GB:
  "${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}"` to the brain, which reads it into
  `config_subagents.py`'s `mem_budget_gb: float = Field(default=8.0, gt=0)`.
- `docker/docker-compose.subagents.yml:158` and `:159` spend the same variable as
  `mem_limit: "${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g"` and the matching `memswap_limit`, where the
  default has to be `8` rather than `8.0` because docker parses the suffix form and `8.0g` is not
  a size it accepts.

So the number lives in three places: the brain's typed field, the env passthrough, and the two
container limits. Raising the field to 12 leaves a container capped at 8 while the admission
scheduler believes it may admit 12 GB of subagents, which is the failure mode the resource
governance work exists to prevent, and nothing reports it: the two compose spellings agree with
each other only by hand, and `crosscheck.py` carries no entry for either.

**What would close it.** One `Constant` in `scripts/couplings.py` whose site is
`config_subagents.py`'s `mem_budget_gb` and whose mentions are the three compose spellings. The
obstacle is that the site declares `Field(default=8.0, gt=0)` rather than a bare number, which
`values.py` refuses to reduce (`parse_value` reads a product of integer literals, a plain string,
or a one-line frozenset, and refuses anything else rather than guessing), and that the two
spellings differ as text (`8.0` against `8`) even when they agree as a number. So the honest
closure is one of: promote the default to a module constant that `values.py` already reads and
have the field cite it; or teach the reducer a float and teach a mention to render a value under a
second spelling. Decide which before writing either, and prove the entry fails by drifting one of
the three places, the way the salience default's was proved.

The wider question this is one instance of, whether every compose default that restates a Python
default should be tied, is deliberately **not** asked here. Around fifty `${CORTEX_*:-default}`
substitutions live under `docker/` and most name a path, a model file or a host-shaped number that
no Python constant declares. This entry is the one case measured to spell a single number in three
places, two of them in the same file.

## Trail

- 2026-08-18: opened by the close of [40](040-salience-limit-knob.md), whose own compose default
  was tied in the same sitting; this is the neighbour that survey found untied.
