# ADR-0006: Check performance via path-filtered CI and a parallel local run

**Status:** Accepted (2026-08-17)

## Context

Measured on the dev machine when `just check` first covered three trees: the full warm run took
about 15 s (brain 7 s, body 6 s, scripts 2 s, linecap 0.2 s) and an incremental Rust change re-ran
in about 4 s. The real costs were elsewhere. A hook defect ran everything twice per commit (fixed).
Cold builds in CI compiled the Rust dependency tree three times (clippy, test and coverage
profiles) on a fresh 2-core runner regardless of what changed, and every push queued a full run
even when a newer push had superseded it.

The repo is headed for open source, so the fixes had to work for contributors on other machines and
for a CI that nobody watches run by run.

## Decision

1. **CI is path-filtered by an in-repo classifier that defaults to running everything**
   (`scripts/ci_paths.py`, stdlib-only, checked like every other script: ruff, pyright strict, 100%
   coverage). A `changes` job computes `git diff --name-only` over the run's range (PR: three-dot
   diff against the base ref; push: `event.before..HEAD` when resolvable) and pipes it into the
   classifier, which emits `python=`/`rust=`/`overlay=`/`shell=` outputs used by job-level `if`s.
   Classification is ordered rules, first match wins, union over all paths:
   - **all:** `justfile`, `.python-version` (exact); `proto/`, `scripts/`,
     `.github/workflows/` (prefix);
   - **python:** `ruff.toml` (exact); `brain/` (prefix);
   - **rust+shell (shell carve-out):** `body/app/src-tauri/` (prefix) is the host-native
     Tauri shell, which is Rust rather than node and is fmt-checked by `check-body`
     (ADR-0011), so it is separated from the overlay by a rule ordered BEFORE `body/app/`.
     It sets `shell=` as well, the one output whose job installs system libraries, so the
     webkit provisioning `check-shell` needs is paid on a shell edit and on nothing else.
     The overlay's tests use a fake bridge and never exercise the shell's Rust, so routing a
     shell edit away from the node job under-tests nothing;
   - **overlay:** `body/app/` (prefix) is the React overlay tree; ordered BEFORE the
     `body/` rule so overlay changes run the node toolchain, not Rust (the overlay is
     excluded from the checked Rust workspace, ADR-0011);
   - **rust:** `body/` (prefix), which includes `os_windows`, clippied for the Windows target
     inside `check-body`;
   - **neither:** `docs/`, `.claude/` (prefix); `.gitignore`,
     `.pre-commit-config.yaml`, `LICENSE`, `.github/dependabot.yml` (exact); `.md`
     (suffix rule, reached only when no earlier rule matched, so `brain/README.md` is
     python; that precedence is deliberate: files inside a toolchain tree are never
     assumed inert, tests may read them as fixtures);
   - **default:** all. Unknown means over-test, never under-test.

   Everything unclear runs everything: unmatched paths run all toolchains, an undeterminable range
   runs all (first push to a branch, or a force-push whose `before` SHA is the zero-SHA or no
   longer fetchable, though an ordinary rebase-force-push keeps a fetchable `before` and takes the
   safe `before..HEAD` diff), and a classifier error fails the run visibly, because the step pipes
   into the classifier under `pipefail`.

   The cross-tree scans are the exception to the filter. They share one unconditional `cross-tree`
   CI job rather than one that is path-filtered, and the comment above that job in
   `.github/workflows/ci.yml` names each scan and the trees it spans. Each one reads more than one
   tree, or a tree no toolchain job covers (`linecap.py` limits `.py`, `.rs`, `.ts` and `.tsx`
   everywhere, `docs/` included; `dashcheck.py` reads every text file; `crosscheck.py` reads
   declaration and use sites in several trees at once,
   [ADR-0042](ADR-0042-cross-tree-constant-registry.md)), so filtering one on a single toolchain's
   paths would let a Rust-only, overlay-only or docs-only change skip it. Locally they are the
   first steps of `just check`, so they fail early.
2. **Cancellation is PR-only**: `concurrency` with `cancel-in-progress` applies only to
   `pull_request` events. Superseded PR pushes cancel (the churny case), but every master commit
   keeps its CI result, because a bisectable history matters for a multi-contributor repo.
3. **`just check` runs the per-tree checks in parallel, in bash 3.2**: the cross-tree scans run
   first, one after another (fast, fail early), then check-brain, check-scripts, check-body and
   check-overlay run concurrently with per-tree buffered output printed in fixed order. Wall time
   is about the slowest tree. The recipe avoids bash-4+ features (`declare -A`) because macOS
   system bash is 3.2 and contributors must be able to run it untouched. Concurrent `uv sync` on
   the scripts venv (check-scripts against check-body's coverage step) is safe, because uv
   serializes per-environment through its own lock.
4. **All actions are named by full commit SHAs.** Release-tagged actions have a `# vN` comment that
   dependabot bumps alongside the SHA; `dtolnay/rust-toolchain` has no releases, so it has a plain
   marker and dependabot advances only its SHA. `.github/dependabot.yml` (github-actions ecosystem,
   weekly) keeps them fresh. Mutable tags are how the tj-actions compromise propagated; a fixed SHA
   turns an action update into a reviewable PR.
5. **Each classifier output controls exactly one CI job, and every result sets all four.**
   `python=` controls the `python` job (`check-brain` and `check-scripts`), `rust=` the `rust` job
   (`check-body`), `overlay=` the `overlay` job (`check-overlay`), and `shell=` the `shell` job,
   which runs `check-shell`, the Tauri shell's clippy. Shell clippy is a separate job rather than a
   step inside `check-body` because it needs the Tauri GTK/webkit/dbus dev packages: folded into
   `check-body`, that install would run on every `body/`, `proto/` and shared-check change to lint
   a subtree most of them do not touch. The `rust+shell` result sets both `rust` (so `check-body`
   still fmt-checks the shell) and `shell`. Every other rule that sets `rust` leaves `shell` false,
   `neither` leaves it false, and both `all` and the default set it true; the workflow's
   no-usable-range branch writes `shell=true` beside the other three. An output that controls one
   job and nothing else is the one a rule can silently drop, leaving that job permanently unrun and
   permanently green, so the classifier's tests assert both directions: a `src-tauri` edit sets
   `shell=true`, and a `body/crates/` plus `body/app/src/` change leaves it false.

## Consequences

- The classification rules are tested code, and a stale rule list **over-tests** rather than
  under-tests: a new cross-tree file defaults to all toolchains. The pressure to keep the rules
  current is economic (wasted CI minutes), not correctness. The rule list here and `RULES` in
  `scripts/ci_paths.py` are one list, changed together.
- Skipped jobs report "skipped", which GitHub branch protection treats as satisfied, and this is
  why filtering uses job-level `if`s fed by a `changes` job rather than `on.push.paths`, which
  would leave required checks pending forever.
- A shell change re-runs the full body coverage build, which over-tests in the safe direction.
- Action version bumps arrive as weekly dependabot PRs; merging them is routine maintenance (each
  one touches `.github/workflows/`, so all toolchains re-run).
- Buffered parallel output means no live streaming per tree; logs print complete, per tree, on
  completion.
- Nothing here checks that the committed `_generated` stubs are current against `proto/body.proto`
  by regenerating them. `scripts/stubcheck.py` ([ADR-0003](ADR-0003-generated-stubs.md) decision 7)
  compares the Rust stub with the proto's comments, which catches a skipped regeneration that
  changed one, and states its own limits.
- The workflows are configuration until Actions is enabled for the repository: no run of either has
  been recorded ([R-594](../refinements/tasks/594-no-workflow-in-this-repository-has-ever-run.md)).

## Alternatives rejected

- **dorny/paths-filter** (briefly adopted). Its hand-maintained shared-file allowlist failed open,
  since a forgotten entry silently under-tests CI, the worst failure mode for a repo heading to
  open source. It is also a mutable-tag third-party action in the same class as
  tj-actions/changed-files, compromised in March 2025 to exfiltrate secrets from thousands of
  repos. This repo already implements its checks as 100%-covered scripts in `scripts/`; the
  classifier follows that pattern.
- **Shell clippy as a step inside `check-body`**: it would put the webkit install on every change
  the rust job runs for (decision 5).
- **`on.push.paths` filtering**: required checks on a skipped workflow stay pending.

## Related

- Code: `scripts/ci_paths.py` and its tests, `.github/workflows/ci.yml`, `.github/dependabot.yml`,
  the `check` recipe in `justfile`.
- Module doc: [repo checks](../modules/repo-checks.md).
- ADRs: [ADR-0002](ADR-0002-toolchain-checks.md) (the checks themselves),
  [ADR-0011](ADR-0011-body-v1.md) (the overlay and shell checks, `check-shell`),
  [ADR-0003](ADR-0003-generated-stubs.md) (the stub check).
