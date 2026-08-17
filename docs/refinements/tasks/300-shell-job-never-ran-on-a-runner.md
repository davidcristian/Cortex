# The shell clippy job has never run on a runner

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** the first CI run whose diff touches `body/app/src-tauri/`, which is the first time
this job executes at all.

**Everything about the shell clippy job was verified locally, and the one thing that cannot be
is the runner half.** The check itself is proven: `just check-shell` exits 0 over the shell and
101 on a planted `useless_format`, and the whole Tauri graph clippies cold in 30.9 s against the
five apt roots the job names, resolved and unpacked here without sudo. The routing is proven:
two tests hold `shell=` on for a `src-tauri` edit and off for any other `body/` change, and
sending that subtree back to plain rust fails the suite. What is unproven is what only GitHub
can run: that `sudo apt-get install --no-install-recommends` of those five roots on
`ubuntu-latest` yields the same pkg-config metadata an `apt-get download` plus `dpkg-deb -x`
yielded here, that `Swatinem/rust-cache` keyed on `body/app/src-tauri` caches a second cargo
workspace in the same repo without colliding with the rust job's, and that a job id of `shell`
raises no complaint from the workflow parser. Each is likely and none is checked, and the repo's
own rule is that a gate which has never run is indistinguishable from one that cannot fail.

The reason this is a follow-up rather than a hole in the landing is that the maintainer pushes
and the agent does not, so the first real execution is a push away and costs nothing to wait
for. It closes on the first CI run whose diff reaches the shell, which is also the first run
that executes the job: green closes it, and a red on the apt line, the cache key or the job id
is a small fix at a known place rather than a re-argued design. Note that the commit landing the
job touches `.github/workflows/` and `justfile`, both shared gate files, so the classifier sets
`shell=true` for that commit and the job runs on its own landing. The measurements it should
confirm, for comparison against whatever the runner reports, are in the origin's 2026-08-17
addendum and in [009](009-shell-clippy-in-ci.md).

## Trail

- 2026-08-17: Filed as the residue of landing shell clippy in CI. The check and the routing were
  both proven able to fail locally; the provisioning, the second workspace's cache key and the
  job id are runner-side and were not.
