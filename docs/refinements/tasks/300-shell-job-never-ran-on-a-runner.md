# The shell clippy job has never run on a runner

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** the first run of `ci.yml` whose `changes` job sets `shell=true`, which is the first
time this job executes at all. None can happen while Actions stays off for the repository, which
is R-594's subject, and the reading is
`gh api repos/<owner>/<repo>/actions/workflows/ci.yml/runs`, whose `total_count` is 0.
**Verified:** 2026-09-17

**Everything about the shell clippy job was verified locally, and the one thing that cannot be
is the runner half.** The check itself is proven: `just check-shell` exits 0 over the shell and
101 on a planted `useless_format`, and the whole Tauri graph clippies cold in 30.9 s against the
five apt roots the job named on 2026-08-17, resolved and unpacked here without sudo. The routing is proven:
two tests hold `shell=` on for a `src-tauri` edit and off for any other `body/` change, and
sending that subtree back to plain rust fails the suite. What is unproven is what only GitHub
can run: that `sudo apt-get install --no-install-recommends` of those five roots on
`ubuntu-latest` yields the same pkg-config metadata an `apt-get download` plus `dpkg-deb -x`
yielded here, that `Swatinem/rust-cache` keyed on `body/app/src-tauri` caches a second cargo
workspace in the same repo without colliding with the rust job's, and that a job id of `shell`
raises no complaint from the workflow parser. Each is likely and none is checked, and the repo's
own rule is that a gate which has never run is indistinguishable from one that cannot fail.

The reason this is a follow-up rather than a hole in the landing is that the maintainer pushes and
the agent does not, so the first real execution was expected a push away. It was not: pushes
carrying a shell edit and a workflow edit have both reached the remote since, and no run followed.
The maintainer's standing answer is that Actions is off for the repository, a setting on the
account and [R-594](594-no-workflow-in-this-repository-has-ever-run.md)'s subject. So this closes
on the first run of the job once that setting changes: a passing run closes it, and a failure on
the apt line, the cache key or the job id is a small fix at a known place rather than a re-argued
design. The commit landing the job touched `.github/workflows/` and `justfile`, both shared gate
files, so the classifier would have set `shell=true` for it had any run happened, and any later
push touching a shared gate file does the same. The measurements it should
confirm, for comparison against whatever the runner reports, are in the origin's 2026-08-17 addendum
and in [009](009-shell-clippy-in-ci.md).

## Trail

- 2026-08-17: Filed as the residue of landing shell clippy in CI. The check and the routing were
  both proven able to fail locally; the provisioning, the second workspace's cache key and the
  job id are runner-side and were not.
- 2026-09-11: read against the tree, and the trigger has not fired: no run of `ci.yml` has ever
  happened, on the standing reading recorded in the entry about no workflow having run, which
  this sweep did not repeat against the API. Everything the entry says about the tree holds. The
  job is still `shell` in `.github/workflows/ci.yml`, gated on the `changes` job's `shell`
  output, cached by `Swatinem/rust-cache` with `workspaces: body/app/src-tauri`, and ends in
  `just check-shell`; the two routing tests are still in `scripts/tests/test_ci_paths.py`. The
  job has grown since this was written, which is where it overlaps the entry about the Windows
  resource step: the apt line now names six packages, the five Linux dev roots and
  `binutils-mingw-w64-x86-64`, the toolchain step adds the `x86_64-pc-windows-msvc` target, and
  `check-shell` runs two clippy lines, so the runner half this entry calls unproven now also
  covers whether that package puts `x86_64-w64-mingw32-windres` where the recipe's default
  expects it and whether the target installs. Both entries close their runner half on this
  trigger. The 30.9 s measurement was not re-run.
- 2026-09-17: read against the remote this time, and not fired. The runs listing for `ci.yml`
  answers `total_count` 0, and the whole repository's four runs are Dependabot update jobs, the
  newest on 2026-09-15. The body's premise that the first run was a push away is refuted rather
  than pending: the 2026-09-13 commit raising the turn's idle gap, which edits
  `body/app/src-tauri/src/seam.rs`, and the 2026-09-11 one repointing the header of
  `.github/workflows/ci.yml`, are both ancestors of `origin/master`, and neither started a run. So the trigger now names the run it waits on and points at the entry about the setting that
  prevents one, and the body says why the wait is longer than it expected. The permissions call
  answers 403 to the token available here, so Actions being off is the maintainer's standing
  answer rather than a reading. The job is as the previous bullet describes it: `shell` at
  `.github/workflows/ci.yml:182`, gated on `needs.changes.outputs.shell`, the six-package apt line
  with `binutils-mingw-w64-x86-64`, the Windows target, `workspaces: body/app/src-tauri`, and
  `just check-shell` last.
