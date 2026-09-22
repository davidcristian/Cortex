# A plain link outside the backlog is resolved by no check

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Verified:** 2026-09-22

`check_links` in `scripts/backlogcheck.py` reads only the task files and the two indexes, as
ADR-0039 decision 7 states. A link from a decision record, a readings record, a runbook or a module
doc is resolved only when it has a `#fragment`, through `scripts/backloganchors.py`. So renaming or
deleting a file leaves every plain link to it from those documents broken, and `just check` passes.
R-700 renamed 97 task files: a stale link in `docs/adr/ADR-0028-grammar-constrained-subagents.md`
to one of them passed `backlogcheck.py`, while the same link in a task file failed it.

**What would close it.** Run `check_links` over every markdown file `backloganchors.markdown_files`
returns rather than the task files alone, and widen decision 7 to say so. A scan with that reach,
run from `local_links` over all 878 markdown files, found no unresolved link on 2026-09-22, so the
wider check passes on the current tree.

## History

- 2026-09-22: opened by R-700, whose rename was checked outside the backlog by a one-off scan.
