# A substitution's several spends may drift from each other with nothing declaring them

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-21 by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md). That
survey settled that a compose default no tree declares is not a coupling and closed the question,
because `scripts/crosscheck.py` compares a declaration against the places restating it and there is
no declaration here to read. It also found the one real defect that answer leaves standing, which
is a different shape and wants its own gate.

**A variable spelled several times must carry one default in all of them.**
`${CORTEX_PG_PASSWORD:-cortex}` appears three times in `docker/docker-compose.memory.yml`, once as
the server's own password and twice as a client's, and `${CORTEX_MODELS_DIR:-./models}` appears in
four compose files that mount one host directory read-only. One spend drifting from its siblings is
a stack that fails at run time in a way nothing static reports: Postgres refusing its own clients,
or one service reading models from a directory the others do not. Neither is exotic, since both are
edited by hand in files a layered override splits across.

**The rule is not "all spellings are identical".** The subagent memory budget is the counterexample
already in the tree: `${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` in an environment block and
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` in two container limits, deliberately, because docker reads
`8.0g` as a size it refuses. So the rule is that the several defaults of one variable must be the
same **value**, and the gate needs the same whole-number spelling `scripts/values.py` already
derives rather than a textual comparison that would call that pair a fault.

**What would close it.** It is a compose-only scan and needs no registry: read every substitution
under `docker/`, group by variable name, and fail a group whose defaults disagree once re-spelling
is allowed. `scripts/composemounts.py` already parses these files for `bindcheck.py`, so the reader
exists. The survey counted 70 substitutions over 56 variables, of which 8 are spelled more than
once, so the gate starts with eight groups to hold and is cheap either way. Whether it
lives in `crosscheck.py` (which would then hold two unrelated questions) or beside `bindcheck.py`
as a second compose-shaped gate is the design decision to record.

## Trail

- 2026-08-21: opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which declined to register these as
  cross-tree couplings and named the defect the decline leaves.
