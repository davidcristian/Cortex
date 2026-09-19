# Nothing counts the commits between replay passes

**Status:** done 2026-09-12
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

The replay pass has a cadence, and the cadence is a count: a pass is due once twenty five candidate
commit bodies have been added since the last row of the ledger in
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md). `just replay "" <date>`
answers that count exactly, and only when somebody runs it, which is the same dependence on a
person remembering that the shuffle review was put on a clock to escape.

The replay itself cannot be scheduled, a runner having no way to rebuild an edit from a sentence,
and a workflow that scheduled only the reminder would keep a calendar the cadence deliberately
rejected. What is mechanical is the comparison: read the last date out of the ledger's bottom row,
count the candidate commit bodies since it, and say whether the number has passed twenty five. That
is a parser over one table plus the `git log` the recipe already runs.

It should not be a `just check` scan, which would fail a commit for a condition no commit caused.
Either a line in `just replay` with no argument, reporting the current count, or the ledger row
becoming machine readable enough for a scan that only ever warns.

## History

- 2026-08-25: opened by the pass that gave the replay a cadence
  ([R-357](357-a-replay-pass-has-no-cadence.md), ADR-0002 decision 20).
- 2026-09-07: not fired, and the prediction the trigger made was wrong.
  `just replay "" 2026-08-25` reports nine candidate commit bodies since the ledger's last row,
  thirteen days after it, so no pass is due at all. The prediction came from the burst the cadence
  decision measured, thirty nine bodies in the four days after the 2026-08-21 pass, and that rate
  did not hold: the sessions since have been mostly documentation closes, which the recipe's
  vocabulary does not match. The trigger now names the number it was always about, fifty, and the
  command that answers it. The nine is the first current count this entry has, and it is evidence
  for the entry rather than against it, since it took a person running the recipe by hand to
  produce a number nothing else was keeping.
- 2026-09-10: still not fired, and the count has grown by six. `just replay "" 2026-08-25` reports
  fifteen candidate commit bodies since the ledger's last row, sixteen days after it, against a
  cadence of twenty five and a trigger of fifty. The rate over the nine days since the last reading
  is under one candidate body a day.
- 2026-09-12: closed, as the first of the two shapes this file proposed. `just replay` with no date
  now prints one line before the draw: the date on the ledger's last dated row, the candidate
  bodies since it, the cadence, and whether the count has reached it. Today's reading is 21 since
  the pass of 2026-08-25, which is what the dated form counts too, against a cadence of 25. The
  threshold is the recipe's own `window` default rather than a new one, the cadence and the draw
  window being one number in two roles, so the line adds no fifth copy of a number
  [R-440](440-the-replay-sample-is-spelled-in-three-places.md) is already about. What closes is the
  asking: the count no longer waits for somebody to hold the ledger's date and the command at the
  same time. Running a pass still starts with a person, which this file's own text declines to
  change. Two residues filed: the ledger's last row is trusted for its format and its order
  ([R-645](645-the-standing-count-takes-the-last-dated-row.md)) and the count reaches back to
  midnight of the pass's own day, which puts two of today's 21 inside the pass that drew them
  ([R-646](646-the-standing-count-includes-the-pass-day.md)). The line is ADR-0002 decision 22,
  measured over four variants of the real ledger.
