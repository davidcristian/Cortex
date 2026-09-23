# scripts/ (`repo-checks`)

**Purpose.** This repo's own checks, in a tree that neither shipped image contains. Thirteen of them
read across every toolchain and run on every change. The rest check one toolchain, one file or one
commit message, or print a measurement and decide nothing. What every module here has in common is
being pure Python that belongs to neither the brain nor the body, tested and typed like both. It is
a standalone uv project, named `repo-checks` in `scripts/pyproject.toml`, rather than a
member of the brain's workspace (ADR-0002).

The detail lives in two companion documents:

- [repo-checks-scans.md](repo-checks-scans.md): what each of the thirteen cross-tree scans
  compares, what fails it, and what it prints.
- [repo-checks-tools.md](repo-checks-tools.md): the Rust coverage check, the CI path classifier,
  the commit-message check, and the five modules that only report a measurement.

## Public contract

Twenty-one modules have a command line. `just` recipes run `linecap.py`, `dashcheck.py`,
`prosecheck.py`, `crosscheck.py`, `bindcheck.py`, `defaultcheck.py`, `volumecheck.py`,
`stubcheck.py`, `samplecheck.py`, `rostercheck.py`, `flagcheck.py`, `settingscheck.py`,
`backlogcheck.py` and `rustcoverage.py`. The CI workflow runs `ci_paths.py`, and the `commit-msg`
hook runs `commitlint.py`. Five measurement reporters have a recipe each: `contrast.py` under
`just turn-cost`, `trailwidth.py` under `just recall-width`, `envelopefloor.py` under
`just envelope-floor`, `envelopepairs.py` under `just envelope-pairs` and `switchtail.py` under
`just switch-tail`. Every one of them also exposes a pure function that another module can import
and a test can call directly.

**The rest have no command line of their own.** Each is read by one of the modules above, and most
were split out of it to stay under the 300-line limit. Grouped by what reads them:

- `crosscheck.py` reads `couplings.py` for the types a registry entry is written with,
  `registry.py` for the parts the registry is joined from, `values.py` for what a value reduces to
  and how a restatement writes it, `readings.py` for whether a set of those values agrees,
  `searchtexts.py` for how a rendered search text is looked for, and `linereadings.py` for what a
  failure reports about one line. The parts themselves are `wirecouplings.py`,
  `endpointcouplings.py`, `shippedcouplings.py`, `boundscouplings.py`, `subagentcouplings.py`,
  `modelhostcouplings.py`, `tracecouplings.py`, `imagecouplings.py`, `emailcouplings.py`,
  `fixturecouplings.py`, `capturecouplings.py`, `overlaycouplings.py`, `logcouplings.py` and
  `trailcouplings.py`.
- `bindcheck.py` reads `composemounts.py` for the mounts one compose file declares.
- `defaultcheck.py` reads `composedefaults.py` for the shell substitutions in one compose file.
- `volumecheck.py` reads `composeservices.py` for what each service runs, covers and is built
  from, with `composetargets.py` for the container path one mount entry gives;
  `imagevolumes.py` for the recorded answer about each image; `dockerfilevolumes.py` for what a
  Dockerfile here declares; and `dockerfilebases.py` for the image its last stage is built on.
  `imagedrift.py` asks a real docker the same questions and prints every row that has changed.
- `stubcheck.py` reads `protocomments.py` for what a comment is on either side of its comparison.
- `samplecheck.py` reads `logsamples.py` for what a documented log line claims to print,
  `logcalls.py` for what the call writing it attaches, `logfields.py` for that call's field list,
  `assertedlines.py` for the lines a package's own suite asserts whole, and `loggernames.py` for
  which module declares a given logger name.
- `rostercheck.py` reads `rosters.py` for every list a document keeps, `rosternames.py` for the
  names written on the page, and `rostermembers.py` for the real set each one describes.
  `scanrecipes.py` answers the one such set that is no directory listing, the scans that both
  `just check` and CI run.
- `flagcheck.py` reads `subagentflags.py` for the flags a subagent server must start with,
  `subagentservers.py` for which compose services start one, `hostedtiers.py` for the tier the
  model host starts itself, `moduleconstants.py` for what a Python module's top level binds, and
  `composestarts.py` for each service's command and environment. Both sets rest on
  `artifactnames.py`, every model file this tree mentions and the variable it is written under.
- `settingscheck.py` reads `settingsfields.py` for the variables one module's settings classes
  read. The stack side comes from the readers above.
- `backlogcheck.py` reads `backlog.py` for the task-file grammar, `backlogindex.py` for the index
  renderer, `backloganchors.py` for the anchors a document offers and the links aimed at them,
  `headingshapes.py` for which headings a slug can be computed from, and `bannedwords.py` for the
  words a task file name may not use. `linecap.py` reads `backlogindex.py` too, for the comment
  that shows a backlog index is generated.
- `prosecheck.py` reads `bannedwords.py` for the word table in AGENTS.md, `prosereaders.py` for
  the prose each file type holds, and `proseliterals.py` for the string literals that hold prose.
  `prosereaders.py` uses `commentblocks.py` for comments and docstrings in Python and
  `slashcomments.py` for comments in Rust, TypeScript, CSS and protobuf, and `proseliterals.py`
  uses `slashcomments.py` for the string literals in Rust and TypeScript and the text between
  JSX tags, `shellstrings.py` for the double-quoted strings in shell, the justfile and TOML, and
  `configstrings.py` for the names, descriptions and `run` steps in YAML.
- `switchtail.py` reads `switchsamples.py`, the file format one run of the thinking-switch probe
  writes. `envelopefloor.py` reads `envelopesamples.py`, the format one variant of the envelope
  measurement writes, and `envelopejudges.py`, the judge declared for each subtask.
  `envelopepairs.py` reads the same format through `envelopesamples.py`.

Six modules are shared rather than owned by one check. `composefiles.py` decides which files the
compose checks walk, so a new override reaches all of them at once. `gitenv.py` is the environment
every git call here runs with, in one place because a caller that omits it reads the wrong
repository without reporting anything. `treewalk.py` is the single descent that hands every reader
its files, and `skippeddirs.py` is the list of directory names it never enters. `scriptcalls.py`
reads out of a module's syntax which calls it makes, which is how the rules about git calls and
tree descents recognize a caller by its shape rather than by how it is written.
`markdownfences.py` defines what a code fence is for the three checks that read documents
containing one.

## How the checks run

`just check` is the single command. It runs the thirteen cross-tree scans first, in the order
`check-linecap`, `check-dashcheck`, `check-prosecheck`, `check-crosscheck`, `check-bindcheck`,
`check-defaultcheck`, `check-volumecheck`, `check-stubcheck`, `check-samplecheck`,
`check-rostercheck`, `check-flagcheck`, `check-settingscheck` and `check-backlog`. It then runs
`check-brain`, `check-scripts`, `check-body` and `check-overlay` in parallel, buffering each tree's
output and printing it under a `=== check-<tree>: OK|FAILED ===` marker.

The pre-commit hook runs the same recipes, and `.github/workflows/ci.yml` mirrors them. The thirteen
scans run unconditionally in CI; the per-toolchain jobs are chosen by `ci_paths.py` from the
changed files. One recipe is deliberately outside `just check`: `check-shell` runs clippy on the
Tauri shell for the host target and for `x86_64-pc-windows-msvc`, and needs system libraries that
a clean dev box need not have, so CI schedules it instead (ADR-0011 decisions 10 and 11).

`just image-volumes` and the five measurement recipes are run by hand. They need a docker daemon or
a GPU, so they record their answer in the tree and a scan compares the record.

## Invariants

- Standard library only. Every module's pure core is unit tested to 100% line and branch coverage,
  and the only coverage pragmas are the `if __name__ == "__main__":` guards.
- The suite runs in a shuffled order under a fixed seed, `--randomly-seed=7919` in `addopts`, as the
  other three tested trees do under their own (ADR-0002 decisions 16 and 17). The order is not the
  collection order and is the same order twice, so a test that depends on a sibling fails here
  every time rather than now and then. The seed is frozen: changing it discards every order the
  suite has already passed. It differs from the brain's, the overlay's and the Rust workspace's on
  purpose. `just shuffle [seed]` is the separate pass over other orders, scheduled weekly by
  `.github/workflows/shuffle.yml`, which decides nothing and is required by nothing. Neither
  workflow has ever run, because GitHub Actions is turned off for this repository.
- Every scan is also run over the committed tree by its own suite, so `check-scripts` reports a
  problem even when the scan's own recipe was not run. Beside each of those sits a second test
  proving the walk read something real: that the repo declares at least six defaulted bind
  sources, that at least six variables have a sibling to disagree with, that both backlog indexes
  are linked to from outside their own directory, that the tree still writes the two heading
  shapes the slug rule must not report, and so on. Without it a reader that stopped matching would
  report a clean tree forever.
- A check that cannot read an input reports a failure rather than passing. A missing file, an
  unreadable one, a syntax the reader was not taught, and a walk that measured nothing are all
  failures, because a scan that read nothing would agree with itself forever.
- The exclusion lists in `linecap.py` and `treewalk.py` are the single definition of "non-test
  source file" and "generated code". Change them only together with ADR-0011 decision 12.
- `dashcheck.py`, `commitlint.py` and their tests write the two dash characters as `\uXXXX`
  escapes rather than as literals, so they pass the rule they enforce.
- `ci_paths.py` runs under a plain `python3` on a GitHub runner before any `uv sync`, so it must
  never grow a third-party import. Its `RULES` table and the rule list in ADR-0006 are the same
  list and change together.

**Dependencies.** Python standard library. Development only: pytest, pytest-cov, pyright, ruff.
