# A substitution's several spends may drift from each other with nothing declaring them

**Status:** landed 2026-08-22
**Area:** repo-gates
**Origin:** [ADR-0026](../../adr/ADR-0026-prose-style-gates.md)

Opened 2026-08-21 by the close of [R-333](333-compose-defaults-that-restate-a-declaration.md). That
survey settled that a compose default no tree declares is not a coupling and closed the question,
because `scripts/crosscheck.py` compares a declaration against the places restating it and there is
no declaration here to read. It also found the one real defect that answer leaves standing, which
is a different shape and needs its own gate.

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
- 2026-08-22: landed as `scripts/defaultcheck.py`, a sixth cross-tree scan beside `bindcheck.py`,
  with `scripts/composedefaults.py` as its substitution reader and `scripts/composefiles.py`
  holding the compose-file walk both compose gates now share. Recorded in the
  [ADR-0026 defaults addendum](../../adr/ADR-0026-prose-style-gates.md#addendum-2026-08-22-a-sixth-cross-tree-scan-over-one-variables-several-compose-defaults),
  which argues the placement against a fold into `crosscheck.py` and carries the proof table.
- 2026-08-22: two counts here were re-derived rather than trusted. **The survey's three numbers were
  exact at the commit that recorded them** (70 substitutions, 56 variables, 8 spelled more than
  once) and read 71 over 57 with the same 8 groups at the commit that closed this, one tool-deadline
  variable having landed between the two readings. **One claim did not survive**: `composemounts.py`
  does not parse these files in any sense this gate could reuse, reading `volumes:` blocks alone,
  where five of the eight groups' spends sit in environment values, a connection string and a
  healthcheck command. Its file discovery was the reusable half and is now shared.
- 2026-08-22: the deferral this close opens is
  [R-385](385-a-note-beside-a-compose-value-is-read-as-a-spend.md), the reader's deliberate
  blindness to a trailing comment marker.
