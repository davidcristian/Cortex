# A failing scheduled run leaves no trace in the repo

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Trigger:** the first run this repository records under `shuffle.yml`, since every remedy below
needs a run to exist and none can. Actions is off for the whole repository, which is a setting on
the account rather than a change in this tree, and R-594 is the entry that waits on the setting.
**Verified:** 2026-09-19

Opened 2026-08-17 by the pass that put the shuffled test run on a weekly schedule
([R-288](288-nothing-schedules-the-shuffle-sweep.md),
[ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 18). Every part of it this repo owns was
proved: the seed is drawn, validated and written to the run summary before the run starts, and the
recipe fails on a planted order dependency and names the test. What was not proved is the last
step. GitHub notifies the account whose commit last touched the cron when a scheduled run fails, so
the only notification is an email governed by settings outside this repo, and nothing in the tree
records that a run happened at all, let alone what seed it drew.

That leaves two failure modes with no evidence in the repo. A failure nobody is notified about sits
in the Actions tab looking exactly like a run nobody has opened yet. And a schedule that stops
firing, which GitHub does to a public repository after 60 days without activity, looks from inside
the repo identical to a schedule that fires and passes.

Three remedies were considered and none taken. A failure step that opens an issue turns the failure
into something somebody has to close, at the cost of widening `permissions` to `issues: write`, a
duplicate-suppression policy, and API logic no local run can exercise. A status badge makes a
failure visible to anyone who opens the README and answers nothing about who looks. A committed
record of each run's seed would make the schedule's silence visible, at the cost of a bot commit in
a history that is deliberately one author's. All three need a run to exist first.

## History

- 2026-09-06: The scheduled run has never happened once. Read over the API with the account's
  token, since this repo has no other channel to its own run history: the runs listing for
  `shuffle.yml` reports `total_count` 0, and so does the same call for `ci.yml`. The only run this
  repository has ever recorded is a Dependabot update on 2026-09-01T17:19:39Z, and both workflows
  were registered at 2026-09-01T17:18:39Z. The cause is one repository setting:
  `repos/<owner>/<repo>/actions/permissions` returns `enabled: false`, so Actions is off for the
  whole repository, while `gh workflow list` still shows every workflow as `active`.
- 2026-09-06: What this entry predicted happened in the sharper of its two forms, and it stayed
  invisible for nineteen days. Of the three remedies, only the committed record of each run's seed
  would have shown it, since a badge and an issue-opening step both need a run to exist. The
  repository setting is filed separately as
  [R-594](594-no-workflow-in-this-repository-has-ever-run.md).
- 2026-09-10: Checked again. `shuffle.yml` and `ci.yml` both report `total_count` 0; the
  repository's whole run history is three Dependabot updates (2026-09-01, 2026-09-08, 2026-09-09);
  both workflows are still listed `active`. The permissions endpoint answers 403 to this token now,
  so the two zero counts are the reading that stands. Monday 2026-09-07 03:41 UTC, the cron's first
  opportunity, produced no run. The 2026-09-06 pass had moved this to actionable on the reasoning
  that the seed record could be built now. It cannot: a step that commits a seed record only writes
  one when a run executes, so nothing built here would be exercised, and it needs a bot author in a
  history that is deliberately one person's, which is the maintainer's decision.
- 2026-09-14: Checked again, not triggered. Both counts still 0, the run history still the same
  three Dependabot updates, the permissions endpoint still 403. Monday 2026-09-14 03:41 UTC passed
  44 minutes before this reading and produced no run, so two consecutive scheduled opportunities
  have fired nothing. Everything above about a weekly schedule is a statement about
  `.github/workflows/shuffle.yml` as a file.
- 2026-09-19: Checked again, not triggered. Both counts still 0; the run history is four Dependabot
  updates, one on 2026-09-15 having joined the three above; the permissions endpoint still answers
  403. No scheduled opportunity has passed since, the next being Monday at 03:41 UTC.
  What changed is outside this entry: the local-dev runbook said the weekly run redraws orders
  without anyone remembering, and it now says the workflow has never run and that `just shuffle` by
  hand is the only way until it does.
