# The shell clippy job has never run on a runner

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** `gh api 'repos/{owner}/{repo}/actions/workflows/ci.yml/runs' --jq .total_count`,
run in the checkout, answers more than 0. The first run of `ci.yml` is the first run of this job,
since every push touching a shared check file sets `shell=true`. None can happen while Actions stays
off for the repository, which is R-594's subject.
**Verified:** 2026-09-22

Everything about the shell clippy job was verified locally except the runner half. The check
itself: `just check-shell` exits 0 over the shell and 101 on a planted `useless_format`, and the
whole Tauri graph clippies from an empty target directory against the five apt roots the job named
on 2026-08-17, resolved and unpacked here without sudo. The routing: two tests require `shell=` on
for a `src-tauri` edit and off for any other `body/` change, and sending that subtree back to plain
rust fails the suite.

What is unproven is what only GitHub can run: that `sudo apt-get install --no-install-recommends`
of those roots on `ubuntu-latest` yields the same pkg-config metadata an `apt-get download` plus
`dpkg-deb -x` yielded here, that `Swatinem/rust-cache` keyed on `body/app/src-tauri` caches a
second cargo workspace in the same repo without colliding with the rust job's, and that a job id of
`shell` raises no complaint from the workflow parser. Each is likely and none is checked, and this
repo's rule is that a check which has never run is indistinguishable from one that cannot fail.

A passing run closes this, and a failure on the apt line, the cache key or the job id is a small
fix at a known place rather than a re-argued design. The measurements it should confirm are in
[the shell clippy readings](../../readings/shell-clippy.md) and in
[009](009-shell-clippy-in-ci.md).

## History

- 2026-08-17: Filed as what was left over from adding shell clippy to CI. The check and the routing
  were both proven able to fail locally; the provisioning, the second workspace's cache key and the
  job id are runner-side and were not.
- 2026-09-11: Checked against the tree, and the trigger has not occurred: no run of `ci.yml` has
  ever happened. The job is still `shell` in `.github/workflows/ci.yml`, conditioned on the
  `changes` job's `shell` output, cached by `Swatinem/rust-cache` with `workspaces:
  body/app/src-tauri`, and ends in `just check-shell`; the two routing tests are still in
  `scripts/tests/test_ci_paths.py`. The job has grown since this was written: the apt line now
  names six packages, the five Linux dev roots and `binutils-mingw-w64-x86-64`, the toolchain step
  adds the `x86_64-pc-windows-msvc` target, and `check-shell` runs two clippy lines, so the runner
  half now also covers whether that package puts `x86_64-w64-mingw32-windres` where the recipe's
  default expects it and whether the target installs. The 30.9 s measurement was not re-run.
- 2026-09-17: Checked against the remote this time, and not triggered. The runs listing for
  `ci.yml` answers `total_count` 0, and the repository's four runs are Dependabot update jobs, the
  newest on 2026-09-15. The entry's premise that the first run was one push away is disproved: the
  2026-09-13 commit raising the turn's idle gap, which edits `body/app/src-tauri/src/brain.rs`, and
  the 2026-09-11 one repointing the header of `.github/workflows/ci.yml`, are both ancestors of
  `origin/master`, and neither started a run. The permissions call answers 403 to the token
  available here, so Actions being off is the maintainer's answer rather than a reading. The job is
  at `.github/workflows/ci.yml:182`.
- 2026-09-22: Not triggered. The trigger's command answers 0, and the repository's runs listing
  holds one run, a Dependabot update job of 2026-09-21. The permissions call still answers 403.
  Two commits on `origin/master` since the last reading each set `shell=true` and started no run:
  the 2026-09-19 fix to the reminder card's ack, which edits
  `body/app/src-tauri/src/reminders.rs`, and the 2026-09-19 trace budget warning, which edits
  `.github/workflows/ci.yml`. The job is at
  `.github/workflows/ci.yml:139`, unchanged: the six apt packages, the `x86_64-pc-windows-msvc`
  target, the cache keyed on `body/app/src-tauri` and `just check-shell`. The two routing tests are
  in `scripts/tests/test_ci_paths.py`, and `scripts/ci_paths.py` still routes
  `body/app/src-tauri/` to `rust+shell` and `.github/workflows/` to every job. The trigger now names
  a command that runs as written, `gh` filling in the owner and repository.
