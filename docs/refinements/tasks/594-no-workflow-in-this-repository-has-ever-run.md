# No workflow in this repository has ever run

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0006](../../adr/ADR-0006-check-performance.md)
**Trigger:** the first run this repository records under either workflow, which needs Actions
enabled for the whole repository and is therefore a setting on the account rather than a change in
this tree.
**Verified:** 2026-09-19

Read on 2026-09-06 over the account's token, in three calls. The runs listing for `shuffle.yml`
under `repos/<owner>/<repo>/actions/workflows` reports `total_count` 0, and the same call for
`ci.yml` reports 0. The repository's whole run history, `repos/<owner>/<repo>/actions/runs`, holds
exactly one entry, a Dependabot update that succeeded on 2026-09-01T17:19:39Z. Both workflows were
registered at 2026-09-01T17:18:39Z. And `repos/<owner>/<repo>/actions/permissions` returns
`enabled: false`, which is Actions being off for the entire repository: the workflows are parsed and
listed as `active`, `gh workflow list` shows all three, and nothing starts them.

`ci.yml` mirrors the local check, and its value is entirely in running what a developer cannot: a
GPU-less runner, a clean checkout, the path classifier deciding which toolchains a diff reaches
([ADR-0006](../../adr/ADR-0006-check-performance.md)), and the system libraries `just check-shell`
needs that `just check` deliberately leaves out ([ADR-0011](../../adr/ADR-0011-body-v1.md) decision
10). None of that has happened once. Three backlog entries wait on a run that cannot occur:
[R-300](300-shell-job-never-ran-on-a-runner.md) waits on the first CI run reaching
`body/app/src-tauri/`, [R-291](291-a-failing-scheduled-run-leaves-no-trace-in-the-repo.md) waits on evidence
that the weekly test-order pass runs, and every claim this repo makes about CI mirroring the local
check is an argument from the workflow file rather than from a result.

Actions being off is the maintainer's current choice rather than an oversight. The setting was read
against the API on 2026-08-31, put to him, and kept off deliberately. A fresh repository defaults to
Actions on, so the state after the 2026-09-01 registration was set rather than inherited. Nobody
should turn the setting on to close this entry.

## History

- 2026-09-06: opened by the trigger check on
  [R-291](291-a-failing-scheduled-run-leaves-no-trace-in-the-repo.md), which fired on its schedule clause.
- 2026-09-09: re-aimed. The tree half stands, and the status was wrong: this was filed as actionable
  while its own text says the close is a setting nobody here may change. It now says what fires it
  and names the one half that is in reach, the wording of the docs that describe CI as something
  that has run.
- 2026-09-11: the tree half was read again and stands, and the remote half was not read. Both
  workflows are still in `.github/workflows/`, and the two entries waiting on a run are both filed
  as waiting for a trigger. No document outside this backlog says the workflows have never run.
- 2026-09-13: read again on both halves, the remote half included. Neither workflow has run: the
  runs listing reports `total_count` 0 for `ci.yml` and 0 for `shuffle.yml`. The repository's run
  history now holds three entries, on 2026-09-01, 2026-09-08 and 2026-09-09, all Dependabot updates.
  The permissions call answers 403 to the token available here, which reports a token scope and not
  a setting, so `enabled: false` stays the 2026-09-06 reading. Two lines of
  [docs/index.md](../../index.md) this entry had called claims that CI had run are instances of the
  repo-wide convention that names the service-less test suite CI, defined in
  [ADR-0068](../../adr/ADR-0068-port-contract-lists.md) and used in about a hundred lines across
  `docs/`, so they are accurate as written.
- 2026-09-19: read again on both halves, not fired. `total_count` is still 0 for both workflows. The
  run history is four entries now, a Dependabot update on 2026-09-15 joining the three above. The
  permissions call still answers 403. The tree half was not finished, as the previous note claimed:
  the two passages that describe the workflows as running, in `docs/runbooks/local-dev-wsl.md` and
  `docs/modules/repo-checks.md`, were never read against this entry. Both now say that neither
  workflow has run, and the runbook names the `gh api` call that reads a workflow's run count, so a
  reader can tell when that changes. Nothing in reach is left and this entry waits only on the
  setting.
