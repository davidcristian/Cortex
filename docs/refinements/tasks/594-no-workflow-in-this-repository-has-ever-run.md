# No workflow in this repository has ever run

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0006](../../adr/ADR-0006-gate-performance.md)

Opened 2026-09-06 by the trigger check on
[R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md), which went looking for a shuffle sweep that
had gone red unread and found instead that neither workflow in this repo has ever executed.

**What was read.** Over the account's token, three calls. The runs listing for `shuffle.yml` under
`repos/<owner>/<repo>/actions/workflows` reports `total_count` 0, and the same call for `ci.yml`
reports 0. The repository's whole run history, `repos/<owner>/<repo>/actions/runs`, holds exactly
one entry, a Dependabot update that succeeded on 2026-09-01T17:19:39Z. Both workflows were
registered at 2026-09-01T17:18:39Z. And `repos/<owner>/<repo>/actions/permissions` returns
`enabled: false`, which is Actions being off for the entire repository: the workflows are parsed
and listed as `active`, `gh workflow list` shows all three, and nothing dispatches them.

**What that costs.** `ci.yml` is the gate mirror, and its value is entirely in running what a
developer cannot: a GPU-less runner, a clean checkout, the path classifier deciding which
toolchains a diff reaches ([ADR-0006](../../adr/ADR-0006-gate-performance.md)), and the system
libraries `just check-shell` needs that `just check` deliberately leaves out
([ADR-0011](../../adr/ADR-0011-body-v1.md) shell-clippy addendum). None of that has happened once.
Three things in the backlog are waiting on a run that cannot occur:
[R-300](300-shell-job-never-ran-on-a-runner.md) waits on the first CI run reaching
`body/app/src-tauri/`, [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md) waits on evidence
that the weekly sweep runs, and every claim this repo makes about CI being a mirror of the local
gate is an argument from the workflow file rather than from a verdict.

**What would close it.** Enabling Actions for the repository, which is a setting on the account
rather than a change in this tree, then reading back that a push produces a CI run and that the
Monday cron produces a sweep. The agent does not push and does not change the account's settings,
so the setting is the maintainer's; the reading afterwards is not, and a run history with entries
in it closes this. Until then the honest statement in any doc that describes CI is that the
workflows are written and unexecuted.

## Trail

- 2026-09-06: opened by the trigger check on
  [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md), which fired on its schedule clause.
