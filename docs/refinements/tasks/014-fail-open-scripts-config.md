# The scripts config that let a new module escape

**Status:** done 2026-07-12
**Area:** repo-checks
**Origin:** [ADR-0062](../../adr/ADR-0062-shared-check-readers.md)

`scripts/pyproject.toml` listed the modules it measured twice, once in the pytest `--cov=` list
and again in pyright's `include`. Adding `dashcheck.py` escaped both the 100% coverage requirement
and strict typing until someone noticed by eye, and the tree still reported 100%, because a module
nobody measures cannot lower the average.

Both now measure the tree rather than a list: `--cov=.` with an explicit coverage omit for
`tests/` and `.venv/`, which leaves test files unmeasured as before, and a pyright `include` of
`"."` with an explicit exclude. A new script is covered by default, and escaping needs a written
exclusion. Checked against an unlisted probe script, which produced 98.62% coverage and two strict
pyright errors, before being relied on.

## History

- 2026-07-12: Closed. `scripts/pyproject.toml` listed its measured modules twice, so `dashcheck.py`
  escaped both coverage and strict typing. Both now measure the tree, and the change was checked
  against an unlisted probe script first.
