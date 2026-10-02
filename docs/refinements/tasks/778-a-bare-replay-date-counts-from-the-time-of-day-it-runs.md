# A bare replay date counts from the time of day the recipe runs

**Status:** open, actionable
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-10-02

`just replay` passes a date to `git log --since` in two places: the late-pass form,
`just replay <seed> <date>`, and the fallback count used when no ledger row's commit resolves. Git
reads a bare date such as `2026-09-19` as that day at the current time of day, not at midnight. On
2026-10-02 at 06:01, `git log --since=2026-09-19` listed 257 commits, the oldest committed at 06:05
on that day, while `git log --since="2026-09-19 00:00"` listed 270, the oldest committed at 03:25.
The candidate pool moves with it. The pass drawn at 05:52 on 2026-10-02 saw 82 candidate bodies
since `2026-09-19`, while the count from the ledger's commit saw 83; the one missing is the commit
that recorded the previous pass, committed at 05:28 on 2026-09-19.

Two written claims fail on this. ADR-0002 decision 22 and
[the runbook](../../runbooks/mutation-replay.md) say the fallback count runs from midnight of the
last dated row. The recipe's line `reproduce this draw with: just replay <seed> <date>, at <commit>`
names a draw that changes with the time of day it is run again, whenever a candidate body was
committed on that date.

**The fix to build.** Read a bare `YYYY-MM-DD` as that day's midnight in both places, by appending
` 00:00` before git reads it, and pass a value that already has a time unchanged. The recipe has no
test, so the change also needs a check that can fail: either a scripts test that runs the recipe in
a scratch repository whose commits are dated around a fixed day, or the date handling moved into a
small script under `scripts/` with its own test. Prove it by removing the suffix and watching the
test fail.

## History

- 2026-10-02: filed by the replay pass of 2026-10-02, whose gap draw saw one candidate body fewer
  than the count from the ledger's commit.
