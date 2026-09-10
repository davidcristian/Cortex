# No workflow in this repository has ever run

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0006](../../adr/ADR-0006-gate-performance.md)
**Trigger:** the first run this repository records under either workflow, which needs Actions
enabled for the whole repository and is therefore a setting on the account rather than a change in
this tree.

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

**What is already decided.** Actions being off is the maintainer's standing choice rather than an
oversight. The setting was read against the API on 2026-08-31, put to him, and kept off
deliberately. A fresh repository defaults to Actions on, so the state after the 2026-09-01
registration was set rather than inherited. This entry therefore waits on a decision that has been
made once already, and nobody should flip the setting to close it.

**What would close it.** Enabling Actions for the repository, which is a setting on the account
rather than a change in this tree, then reading back that a push produces a CI run and that the
Monday cron produces a sweep. The agent does not push and does not change the account's settings,
so the setting is the maintainer's; the reading afterwards is not, and a run history with entries
in it closes this. Until then the honest statement in any doc that describes CI is that the
workflows are written and unexecuted.

**What is in reach before that, and is not started.** No doc here says the workflows have never
run. Two lines of [docs/index.md](../../index.md) say the opposite in passing, one pointing at the
architecture record's contract-test addendum as naming "which implementations CI actually drives it
against" and one describing the pgvector adapter's behaviour as "proven against the fake in CI".
Both describe what the workflow file specifies and read as a report of runs that happened. Wording
those as the workflow's instruction rather than as a verdict is a change anyone can make in this
tree, and it is what this entry can deliver while the setting stays off.

## Trail

- 2026-09-06: opened by the trigger check on
  [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md), which fired on its schedule clause.
- 2026-09-09: re-aimed by the premise sweep, which held the tree half of this entry to the code and
  left the remote half alone. The tree half stands: `ci.yml` is still the gate mirror,
  [R-300](300-shell-job-never-ran-on-a-runner.md) still waits on the first run reaching the shell,
  and [R-291](291-a-red-sweep-leaves-no-trace-in-the-repo.md) still waits on evidence that the sweep
  runs. The state was wrong. This was filed as actionable now while its own text says the close is a
  setting nobody here may flip, and [R-300](300-shell-job-never-ran-on-a-runner.md), which waits on
  the same event, is filed as fix when it bites. It now says what fires it, and names the one half
  that is in reach meanwhile, the wording of the docs that describe CI as a thing that has run. The
  three API readings above are the maintainer's standing answer of 2026-09-06 rather than a fresh
  one, so this entry carries no verified date: a claim about a remote service is not held to the
  code.
- 2026-09-11: the tree half was read again and stands, and the remote half was not read, since
  Actions being off is a setting on the account and this sweep held the check to the tree. Both
  workflows are still in `.github/workflows/`, `ci.yml` still describes the gate mirror, and the
  two entries waiting on a run are both still filed as fix when it bites. The two lines of
  `docs/index.md` this entry names still read as verdicts, at lines 27 and 78, and no document
  outside this backlog says the workflows have never run, so the half that is in reach is still
  not started. No verified date, for the reason the previous bullet gives.
