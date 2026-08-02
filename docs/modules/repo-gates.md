# scripts/ (`repo-gates`)

**Purpose.** The repo's own gate tooling: the cross-tree line cap, the punctuating-dash
ban, the cross-language constant check, the Rust branch coverage threshold, the CI path
classifier, and the commit-message style hook. A standalone uv project (not a brain
workspace member, per ADR-0002), gated exactly like all other Python.

**Public contract** (all are CLIs, with `linecap.py`, `dashcheck.py`, `crosscheck.py` and
`coverage_gate.py` invoked by `just` recipes, `ci_paths.py` by the CI workflow,
`commitlint.py` by the commit-msg pre-commit stage; each also exposes a pure, unit-tested
core function).

- `linecap.py [--root DIR] [--max-lines N]` implements AGENTS.md gate 1. Scans
  `*.py`/`*.rs`/`*.ts`/`*.tsx` under `--root` (default `.`), all three gated toolchains
  since the ADR-0011 line-cap addendum, counting ALL lines (code, comments, blanks; cap
  default 300). Stylesheets, markup and `proto/body.proto` are outside the cap by that same
  addendum. Skips dir components `.git`, `.venv`, `.claude`, `target`, `node_modules`,
  `__pycache__`, `.pytest_cache`, `.ruff_cache`, `dist`, `coverage`, `tests`, `_generated`
  (the generated-code marker), and test-named files (`test_*.py`, `*_test.py`,
  `conftest.py`, `*_test.rs`, `*.test.ts`, `*.test.tsx`, `test-setup.ts`, the last three
  being what `body/app/vite.config.ts` collects and sets up). `*.d.ts` is NOT exempt.
  Directory symlinks are not traversed (deliberate: no
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
  `_generated`, since prose in a test or a generated stub is still prose, and
  `test_skipped_dirs_match_dashcheck_plus_tests_and_generated` holds the two lists to that
  sentence rather than leaving it to be believed; binary files are
  detected and skipped. A line carrying `dashcheck: allow` plus a reason is exempt, for a
  dash that means rather than punctuates. Exit 0 with a summary; exit 1 printing
  `path:line: kind: text` per violation; exit 2 if `--root` is not a directory or a file
  cannot be read.
- `crosscheck.py [--root DIR]` ties the constants that exist once per language because both
  sides of the seam must hold the same value and neither toolchain can import the other's
  (ADR-0029 cross-language-constant addendum). `CONSTANTS` is the registry: each entry is a
  label, the reason the sites must agree (printed with any failure), and two or more `Site`s,
  each a repo-relative path plus the identifier declared in it. Registered today: the
  screen-capture byte ceiling (`MAX_CAPTURE_BYTES` in `body/crates/core`, `MAX_IMAGE_BYTES` in
  `brain/packages/core`), the seam token's metadata key (`SEAM_TOKEN_HEADER` in
  `body/crates/rpc`'s `auth.rs` and `client.rs`, and in `brain/packages/seam`), and the
  session-title truncation bound (`TITLE_MAX` in `brain/packages/core`'s `sessions.py` and in the
  overlay's `sessionState.ts`, ADR-0021 truncation addendum).
  **No master:** the sites are compared with each other, not against a declared value, so
  editing either side alone fails and a deliberate change is a change to all of them.
  `proto/body.proto` is not the source: protobuf has no constant, so a value could only sit
  there as a comment, which is one more uncoupled copy. Values are compared after reduction,
  so `6291456` and `6 * 1024 * 1024` tie; the two forms that reduce are a product of integer
  literals and a plain double-quoted string, and `DECLARATIONS` holds one declaration syntax
  per language (`.py`, `.rs`, `.ts`), matching module-level and item-level constants only: the
  Python and TypeScript forms are anchored at column 0, so an indented `const` is a local and not
  a second declaration of the module's constant.
  **Fails closed by design**, because a scan that cannot find its constants would agree with
  itself forever: a missing file, an unreadable or non-UTF-8 one, an unknown suffix, a name
  that is absent, one declared twice, a value it cannot reduce, and a registry entry naming
  fewer than `MIN_SITES` (2) are each a fault, never a skip. Exit 0 with a summary; exit 1
  printing `label: detail` per fault; exit 2 if `--root` is not a directory.
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
  (the overlay = the `body/app/` React tree, gated by `check-overlay`; its Tauri shell
  subtree `body/app/src-tauri/` is Rust and is carved back to `rust`), and nothing else.
  Logs one `ci-paths: PATH -> VERDICT` line per path to stderr so CI logs show why a job
  ran. Empty input yields all three `false`. Unmatched paths fail closed to ALL three
  (unknown means over-test, never under-test). Always exits 0, because classification has no
  failure mode.
- `commitlint.py MESSAGE_FILE [--repo DIR]` is the machine-checkable half of the AGENTS.md
  commit rules, run at the commit-msg stage next to conventional-pre-commit. Checks the
  header (first non-comment line): ≤ 72 chars, lowercase subject, no trailing period. A
  header that is not Conventional-Commits-shaped passes silently (structure errors are the
  other hook's to report); `Merge `/`fixup! `/`squash! `/`amend! ` headers are exempt, body
  rules included, because that wording is git's and not the author's. Every line BELOW the
  header must wrap at 72 (`MAX_BODY_WIDTH`, the same number the header is capped at, checked
  separately so one long subject is one complaint): a line past it that could have been wrapped
  fails, and `too_wide` exempts one whose longest word alone is over the wrap, since a URL, a
  path, or a long identifier has nowhere to break and demanding a rewrite that cannot exist
  would train authors to ignore the gate. Four 73-character lines reached master before this
  landed, which is what it was added for. Across the WHOLE
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
- `crosscheck.py`'s registry is checked against the real trees by its own suite
  (`test_the_repo_itself_is_tied`), so `check-scripts` catches a drift even when
  `check-crosscheck` is not the recipe that runs. Registering a constant in a language
  `DECLARATIONS` does not know, or inside a single tree, is refused by that suite too.
- The exclusion lists above are the single definition of "non-test source file" and
  "generated code" for the cap. Change them only with an ADR update.
- `dashcheck.py`, `commitlint.py`, and their tests spell the dashes as `\uXXXX` escapes
  rather than literals, so the gates pass the rule they enforce. A literal would make the
  gate flag itself.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner **before** any `uv
  sync`: it must never grow a third-party import. Its `RULES` table and the rule list
  in ADR-0006 are the same normative list, so change them together.

**Dependencies.** Python stdlib; dev-only: pytest, pytest-cov, pyright, ruff.
