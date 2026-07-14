# scripts/ (`repo-gates`)

**Purpose.** The repo's own gate tooling: the cross-tree line cap, the punctuating-dash
ban, the Rust branch coverage threshold, the CI path classifier, and the commit-message
style hook. A standalone uv project (not a brain workspace member, per ADR-0002), gated
exactly like all other Python.

**Public contract** (all are CLIs, with `linecap.py`, `dashcheck.py`, and
`coverage_gate.py` invoked by `just` recipes, `ci_paths.py` by the CI workflow,
`commitlint.py` by the commit-msg pre-commit stage; each also exposes a pure, unit-tested
core function).

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
- `dashcheck.py [--root DIR]` implements the no-dash-as-punctuation rule (ADR-0026).
  Scans EVERY text file under `--root` (default `.`), not just `*.py`/`*.rs`, because the
  rule covers docs and comments alike. Flags U+2014 EM DASH and U+2013 EN DASH anywhere,
  spaced or not, since a range takes a plain ASCII hyphen. Deliberately silent on U+2212
  MINUS SIGN (arithmetic), and on ASCII `--` (the repo's inline-reason idiom, which the gate-2
  escape-hatch rule effectively requires; commit messages are stricter and `commitlint.py`
  bans it there). Skips the same directory components as `linecap.py` minus `tests` and
  `_generated`, since prose in a test or a generated stub is still prose; binary files are
  detected and skipped. A line carrying `dashcheck: allow` plus a reason is exempt, for a
  dash that means rather than punctuates. Exit 0 with a summary; exit 1 printing
  `path:line: kind: text` per violation; exit 2 if `--root` is not a directory or a file
  cannot be read.
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
- `commitlint.py MESSAGE_FILE [--repo DIR]` is the machine-checkable half of the AGENTS.md
  commit rules, run at the commit-msg stage next to conventional-pre-commit. Checks the
  header (first non-comment line): ≤ 72 chars, lowercase subject, no trailing period. A
  header that is not Conventional-Commits-shaped passes silently (structure errors are the
  other hook's to report); `Merge `/`fixup! `/`squash! `/`amend! ` headers are exempt, body
  rules included, because that wording is git's and not the author's. Across the WHOLE
  message (subject and body) it also bans a dash used as punctuation (em dash, en dash,
  spaced ASCII `--`, since a message is pure prose) and volatile references: a slice
  number, a decision-record number, the roadmap, or a numbered assumption/increment/gate/
  decision/audit. Hex tokens are resolved against `--repo` (default `.`) with `git
  cat-file`, so ONLY a hash that really is a commit is reported: a rewrite invalidates it,
  while action SHAs and digests stay legal. If `git` is unavailable the hash check cannot
  disprove anything and passes rather than blocking the commit. Imperative mood is not
  machine-checkable and stays convention. Exit 0 clean; exit 1 printing one
  `commitlint: PROBLEM` line per violation; argparse exit 2 on usage errors.
  That `git` call, and every one its tests make, runs with git's own variables stripped
  from the environment: these gates execute inside hooks, where git exports `GIT_DIR`, and
  that variable OUTRANKS `-C`. Inheriting it silently retargets the call at the repository
  git is mid-commit in, which answered the hash question about the wrong object database
  and, in the tests, staged a fixture file into the in-flight commit's own index.

**Invariants.**
- stdlib-only modules; pure cores (`scan`, `evaluate`/`check`, `classify`) unit-tested
  to 100% line+branch; the only coverage pragmas are the `__main__` guard lines.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `dashcheck.py`, `commitlint.py`, and their tests spell the dashes as `\uXXXX` escapes
  rather than literals, so the gates pass the rule they enforce. A literal would make the
  gate flag itself.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
