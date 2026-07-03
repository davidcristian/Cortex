# scripts/ (`repo-gates`)

**Purpose.** The repo's own gate tooling: the cross-tree line cap, the Rust branch
coverage threshold, the CI path classifier, and the commit-subject style hook. A
standalone uv project (not a brain workspace member, per ADR-0002), gated exactly like all
other Python.

**Public contract** (all are CLIs, with `linecap.py` and `coverage_gate.py` invoked by
`just` recipes, `ci_paths.py` by the CI workflow, `commitlint.py` by the commit-msg
pre-commit stage; each also exposes a pure, unit-tested core function).

- `linecap.py [--root DIR] [--max-lines N]` implements AGENTS.md gate 1. Scans `*.py`/`*.rs`
  under `--root` (default `.`), counting ALL lines (code, comments, blanks; cap default
  300). Skips dir components `.git`, `.venv`, `.claude`, `target`, `node_modules`,
  `__pycache__`, `.pytest_cache`, `.ruff_cache`, `tests`, `_generated` (the
  generated-code marker), and test-named files (`test_*.py`, `*_test.py`,
  `conftest.py`, `*_test.rs`). Directory symlinks are not traversed (deliberate: no
  cycles, no escapes outside the root); a candidate that is not a regular file after
  following symlinks (e.g. a dangling editor-lockfile symlink) is skipped.
  Exit 0 with a summary line; exit 1 printing `path: N lines (cap M)` per violation;
  exit 2 if `--root` is not a directory or a source file cannot be read.
- `coverage_gate.py PATH` reads a `cargo llvm-cov --json --summary-only` export,
  requires exactly one `data[]` entry, and gates each of
  `data[0].totals.{lines,regions,branches}` on `covered == count` (the producer's
  `percent` is never trusted; displayed percentages are recomputed). A metric with
  `count == 0` passes vacuously (with a printed note). Malformed/missing/non-UTF-8
  input → typed error, exit 1. Exit 0 only when all three metrics pass.
- `ci_paths.py` implements AGENTS.md gate 3 / ADR-0006. Decides which toolchain CI jobs must run
  for a set of changed files. Reads newline-separated repo-relative paths (the output of
  `git diff --name-only`) on stdin; blank lines are ignored. Each path is classified by
  ordered rules, first match wins (the normative rule list lives in ADR-0006); the
  result is the union over all paths. Writes exactly three `GITHUB_OUTPUT`-format lines
  to stdout, in order: `python=true|false`, `rust=true|false`, then `overlay=true|false`
  (the overlay = the `body/app/` React tree, gated by `check-overlay`), and nothing else.
  Logs one `ci-paths: PATH -> VERDICT` line per path to stderr so CI logs show why a job
  ran. Empty input yields all three `false`. Unmatched paths fail closed to ALL three
  (unknown means over-test, never under-test). Always exits 0, because classification has no
  failure mode.
- `commitlint.py MESSAGE_FILE` is the machine-checkable half of the AGENTS.md commit
  rules, run at the commit-msg stage next to conventional-pre-commit. Checks the header
  (first non-comment line): ≤ 72 chars, lowercase subject, no trailing period. A header
  that is not Conventional-Commits-shaped passes silently (structure errors are the
  other hook's to report); `Merge `/`fixup! `/`squash! `/`amend! ` headers are exempt.
  Imperative mood is not machine-checkable and stays convention. Exit 0 clean; exit 1
  printing one `commitlint: PROBLEM: HEADER` line per violation; argparse exit 2 on
  usage errors.

**Invariants.**
- stdlib-only modules; pure cores (`scan`, `evaluate`/`check`, `classify`) unit-tested
  to 100% line+branch; the only coverage pragmas are the `__main__` guard lines.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
