# A red sweep leaves no trace in the repo

**Status:** open, actionable
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-17 by the pass that put the shuffle sweep on a clock
([R-288](288-nothing-schedules-the-shuffle-sweep.md), [ADR-0002 sweep-schedule
addendum](../../adr/ADR-0002-toolchain-gates.md)). The sweep is scheduled weekly, and every part
of it this repo owns was proved: the seed is drawn, validated, written to the run summary before the sweep
starts, and the recipe fails on a planted order dependency and names the test. What was not proved,
because proving it means firing the real thing, is the last hop. GitHub's documented behaviour is to
notify the account whose commit last touched the cron when a scheduled run fails, so the failure's
only push channel is an email governed by settings that live outside this repo, and nothing in the
tree records that a sweep ran at all, let alone what seed it drew.

That leaves two failure modes with no in-repo evidence. A failure nobody is notified about sits in
the Actions tab looking exactly like a run nobody has opened yet. And a schedule that stops firing,
which GitHub does to a public repository after 60 days without activity, looks from inside the repo
identical to a schedule that fires and passes: the absence of a failure.

**What would close it, and why none of it was taken now.** A failure step that opens an issue is the
obvious shape and the one that turns the failure into a durable artifact somebody has to close, at
the cost of widening `permissions` to `issues: write`, of a duplicate-suppression policy so a red
that persists for a month does not file four issues, and of API logic that no local run can
exercise, which is the same untestable hop one layer further in. A status badge makes a failure
visible to anyone who opens the README and answers nothing about who looks. A committed record of
each run's seed would make the schedule's silence legible, at the cost of a bot commit on a repo
whose history is deliberately one author's. All three are worth less than the first evidence that a
real failure went unread, which is the trigger above; until then the sweep gates nothing, so the
cost of reading it late is bounded by how long the pair it names has already been latent.

## Trail

- 2026-09-06: **The trigger fired on its schedule clause, and the answer is larger than the clause
  asked for: the sweep has never run once.** Read over the API with the account's token, since this
  repo has no other channel to its own run history. The runs listing for `shuffle.yml` under
  `repos/<owner>/<repo>/actions/workflows` reports `total_count` 0, and so does the same call for
  `ci.yml`. The only run this
  repository has ever recorded is a Dependabot update on 2026-09-01T17:19:39Z, and both workflows
  were registered at 2026-09-01T17:18:39Z, a minute before it. The cause is one repository setting:
  `repos/<owner>/<repo>/actions/permissions` returns `enabled: false`, so Actions is off for the
  whole repository. Every workflow is still listed as `active` by `gh workflow list`, which is what
  makes the state invisible from a listing as well as from the tree. The sweep therefore has no red
  to have been read late; it has no run at all, on a schedule that has never fired, and the first
  reading of that fact is this one, nineteen days after the cron landed.
- 2026-09-06: what this entry predicted is exactly what happened, in the sharper of the two forms it
  named. A schedule that never fires looks from inside the repo identical to one that fires and
  passes, and it stayed that way for nineteen days. Of the three remedies argued above, the
  committed record of each run's seed is the only one that would have surfaced it, because a badge
  and an issue-opening failure step both need a run to exist before they say anything. That moves
  this entry to actionable and changes what it is for: not a channel for a red, but evidence that
  the sweep ran. The repository setting behind it is a separate piece of work and is filed as
  [R-594](594-no-workflow-in-this-repository-has-ever-run.md) rather than started here.
