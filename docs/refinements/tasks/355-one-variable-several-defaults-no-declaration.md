# One variable's several compose defaults can disagree, with nothing declaring the value

**Status:** done 2026-08-22
**Area:** repo-checks
**Origin:** [ADR-0063](../../adr/ADR-0063-compose-checks.md)

[R-333](333-compose-defaults-that-restate-a-declaration.md) settled that a compose default no tree
declares is not a cross-tree pair, because `scripts/crosscheck.py` compares a declaration against
the places restating it and there is no declaration here. It also found the one real defect that
answer leaves.

A variable used several times must have one default in all of them.
`${CORTEX_PG_PASSWORD:-cortex}` appears three times in `docker/docker-compose.memory.yml`, once as
the server's own password and twice as a client's, and `${CORTEX_MODELS_DIR:-./models}` appears in
four compose files that mount one host directory read-only. One of them differing from its siblings
is a stack that fails at run time in a way nothing static reports: Postgres refusing its own
clients, or one service reading models from a directory the others do not.

The rule is not that all the text is identical. The subagent memory budget is the counterexample:
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8.0}` in an environment block and
`${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g` in two container limits, deliberately, because docker reads
`8.0g` as a size it refuses. So the rule is that the several defaults of one variable must be the
same value, using the whole-number form `scripts/values.py` already computes.

It is a compose-only scan and needs no registry: read every substitution under `docker/`, group by
variable name, and fail a group whose defaults disagree once a second written form is allowed. The
survey counted 70 substitutions over 56 variables, of which 8 appear more than once, so the scan
starts with eight groups. Whether it lives in `crosscheck.py` or beside `bindcheck.py` as a second
compose scan is the design decision to record.

## History

- 2026-08-21: Opened by the close of
  [R-333](333-compose-defaults-that-restate-a-declaration.md), which declined to register these as
  cross-tree pairs and named the defect that leaves.
- 2026-08-22: Built as `scripts/defaultcheck.py`, a sixth cross-tree scan beside `bindcheck.py`,
  with `scripts/composedefaults.py` as its substitution reader and `scripts/composefiles.py`
  holding the compose-file walk both compose scans now share. The placement against folding it into
  `crosscheck.py` is argued in [ADR-0063](../../adr/ADR-0063-compose-checks.md), decision 6.
- 2026-08-22: Two counts here were checked rather than trusted. The survey's three numbers were
  exact at the commit that recorded them (70 substitutions, 56 variables, 8 used more than once)
  and read 71 over 57 with the same 8 groups at the commit that closed this, one tool-deadline
  variable having arrived between the two readings. One claim did not survive: `composemounts.py`
  does not parse these files in any way this scan could reuse, reading `volumes:` blocks alone,
  where five of the eight groups sit in environment values, a connection string and a healthcheck
  command. Its file discovery was the reusable half and is now shared.
- 2026-08-22: The follow-up this close opens is
  [R-385](385-a-note-beside-a-compose-value-is-read-as-a-spend.md), the reader's deliberate
  blindness to a trailing comment marker.
