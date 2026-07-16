# ADR-0006: Gate performance via path-filtered CI and a parallel local gate

- **Status:** Accepted
- **Date:** 2026-06-29

## Context

Measured on the dev machine after Slice 3: the full warm gate is ~15 s (brain 7 s,
body 6 s, scripts 2 s, linecap 0.2 s) and an incremental Rust change re-gates in ~4 s.
The real costs were elsewhere: a hook bug ran the entire gate twice per commit (fixed
as a defect, `a51ce2d`), and cold builds, where CI compiles the Rust dependency tree three
times (clippy/test/coverage profiles) on a fresh 2-core runner regardless of what
changed, and every push queued a full run even when a newer push had superseded it.

The decisions were revised same-day, pre-push, for open-source longevity.

## Decisions

1. **CI is path-filtered by an in-repo, fail-closed classifier** (`scripts/ci_paths.py`,
   stdlib-only, gated like every other script: ruff, pyright strict, 100% coverage).
   A `changes` job computes `git diff --name-only` over the run's range (PR: three-dot
   diff against the base ref; push: `event.before..HEAD` when resolvable) and pipes it
   into the classifier, which emits `python=`/`rust=`/`overlay=` outputs consumed by
   job-level `if`s. Classification is ordered rules, first match wins, union over all paths:
   - **all:** `justfile`, `.python-version` (exact); `proto/`, `scripts/`,
     `.github/workflows/` (prefix);
   - **python:** `ruff.toml` (exact); `brain/` (prefix);
   - **rust (shell carve-out):** `body/app/src-tauri/` (prefix) is the host-native Tauri
     shell, which is Rust rather than node and is fmt-checked by `check-body` (ADR-0011),
     so it is carved back to rust by a rule ordered BEFORE `body/app/`;
   - **overlay:** `body/app/` (prefix) is the React overlay tree; ordered BEFORE the
     `body/` rule so overlay changes gate the node toolchain, not Rust (the overlay is
     excluded from the gated Rust workspace, ADR-0011);
   - **rust:** `body/` (prefix);
   - **neither:** `docs/`, `.claude/` (prefix); `.gitignore`,
     `.pre-commit-config.yaml`, `LICENSE`, `.github/dependabot.yml` (exact); `.md`
     (suffix rule, reached only when no earlier rule matched, so `brain/README.md` is
     python; that precedence is deliberate: files inside a toolchain tree are never
     assumed inert, tests may read them as fixtures);
   - **default:** all. Unknown means over-test, never under-test.
   Fail-closed everywhere: unmatched paths run all toolchains, an undeterminable range
   runs all (first push to a branch, or a force-push whose `before` SHA is the zero-SHA
   or no longer fetchable, though an ordinary rebase-force-push keeps a fetchable `before` and
   takes the safe `before..HEAD` diff), and a classifier error fails the run visibly.
   *Alternative considered and rejected:* dorny/paths-filter (briefly adopted
   in `aaf4f38`). Its hand-maintained shared-file allowlist was fail-open, since a forgotten
   entry silently under-tests CI, the worst failure mode for a repo heading to open
   source. It is also a mutable-tag third-party action in the same class as
   tj-actions/changed-files, compromised in March 2025 to exfiltrate secrets from
   thousands of repos. This repo already owns its gates as 100%-covered scripts in
   `scripts/`; the classifier follows that pattern.
   The line-cap gate is the one exception to the filter: `linecap.py` scans `.py` and
   `.rs` across every tree (`docs/` included), so `check-linecap` runs as its own
   unconditional CI job rather than inside a path-gated one. Otherwise a Rust-only or
   docs-only change would skip the cross-tree cap. Locally it stays the fail-early first
   step of `just check`.
2. **Cancellation is PR-only**: `concurrency` with `cancel-in-progress` applies only to
   `pull_request` events. Superseded PR pushes cancel (the churny case), but every
   master commit keeps its CI verdict, because a bisectable history matters for a
   multi-contributor repo.
3. **`just check` parallelizes the tree checks, in bash 3.2**: linecap runs first
   (fast, fail-early), then check-brain / check-scripts / check-body run concurrently
   with per-tree buffered output printed in fixed order. Wall time ≈ the slowest tree.
   The recipe avoids bash-4+ features (`declare -A`) because macOS system bash is 3.2 and
   contributors must be able to run the gate untouched. Concurrent `uv sync` on the
   scripts venv (check-scripts vs. check-body's gate step) is safe, because uv serializes
   per-environment via its own lock.
4. **All actions are pinned to full commit SHAs.** Release-tagged actions carry a `# vN`
   comment that dependabot bumps alongside the SHA; `dtolnay/rust-toolchain` has no
   releases, so it carries a plain marker and dependabot advances only its SHA. A new
   `.github/dependabot.yml` (github-actions ecosystem, weekly) keeps the pins fresh.
   Mutable tags are how the tj-actions compromise propagated; pinned SHAs turn action
   updates into reviewable PRs.

## Consequences

- The classification rules are tested code, and a stale rule list **over-tests** rather
  than under-tests: a new cross-tree file simply defaults to all toolchains. The
  pressure to keep the rules current is economic (wasted CI minutes), not correctness.
- Skipped jobs report "skipped", which GitHub branch protection treats as satisfied, and
  this is why filtering is job-level `if`s fed by a `changes` job rather than
  `on.push.paths`, which would leave required checks pending forever.
- The line-cap gate runs unconditionally, outside the filter: it is cross-tree (`.py` +
  `.rs`, `docs/` included), so gating it on any one toolchain's paths would let a
  Rust-only or docs-only change merge an over-cap file green.
- Action version bumps now arrive as weekly dependabot PRs; merging them is routine
  maintenance (each touches `.github/workflows/`, so all toolchains re-gate).
- Buffered parallel gate output means no live streaming per tree; logs print complete,
  per tree, on completion.
- Observed adjacent gap while writing the filters (not addressed here): nothing in CI
  verifies the committed `_generated` stubs are fresh against `proto/body.proto`; a
  stub-freshness check would close it (candidate for the next seam-touching slice).

## Addendum (2026-07-01): `overlay` as a third toolchain dimension (Slice 8)

Slice 8 (ADR-0011) added the React overlay under `body/app/`, gated at 100% by
`just check-overlay` (a host-only node toolchain: npm + Vitest + v8, no GPU/webkit). The
classifier grew a **third** output, `overlay=`, alongside `python=`/`rust=`, and a new
`overlay` CI job gated on it (`actions/setup-node`, then `just check-overlay`). Two
consequences of that split, kept normative here with the rule list above:

- The shared-gate verdict `BOTH` was renamed `ALL` (it now unions three toolchains, not
  two); the `DEFAULT` fail-closed verdict likewise runs all three.
- `body/app/` classifies as **overlay-only** and its rule is ordered **before** `body/` →
  rust. The Tauri `src-tauri` shell lives in the same `body/app/` tree but is excluded
  from the gated Rust workspace and host-validated (ADR-0011 decision 5), so a change
  anywhere under `body/app/` gates the node toolchain in CI, never the Rust one.

## Addendum (2026-07-16): the Tauri shell subtree is carved back to rust

The rule above sent *every* `body/app/` change to the overlay (node) job, including the
host-native Tauri shell at `body/app/src-tauri/`, which is Rust, not node. That was correct
while nothing gated the shell's Rust, but `check-body` now fmt-checks the shell (ADR-0011),
and a fmt gate is only real if the change that would dirty it triggers the job that runs it.
So a fourth `body/app/` ordering was added: `body/app/src-tauri/` → **rust**, placed BEFORE
the `body/app/` → overlay rule (first match wins). A shell `.rs` edit now gates the rust
job (which runs `just check-body`, hence the shell fmt check), while the React overlay under
`body/app/src/` stays overlay. The React tests use a fake bridge and never exercise the shell
Rust, so routing a shell-only change away from the node job under-tests nothing; and a shell
change re-running the full body coverage build is over-testing, the safe direction the
classifier already prefers. `os_windows` needed no classifier change: it lives under `body/`
and already gated the rust job; `check-body` just clippy-checks it on the windows target now.
