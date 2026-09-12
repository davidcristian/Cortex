# Nothing counts the record between replay passes

**Status:** landed 2026-09-12
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

Opened 2026-08-25 by the pass that gave the replay a cadence
([R-357](357-a-replay-pass-has-no-cadence.md), [ADR-0002 replay-cadence
addendum](../../adr/ADR-0002-toolchain-gates.md)). The cadence is a count: a pass is due once
twenty five candidate bodies have landed since the last row of the ledger in
[docs/runbooks/mutation-replay.md](../../runbooks/mutation-replay.md). `just replay "" <date>`
answers that count exactly, and it answers it only when somebody runs it, which is the same
dependency on somebody remembering that the shuffle sweep was put on a clock to escape.

**Why it was left this way.** The replay itself cannot be scheduled, a runner having no way to
rebuild an edit from a sentence, and a workflow that scheduled only the reminder would keep a
calendar the cadence deliberately rejected. What is genuinely mechanical is the comparison: read
the last date out of the ledger's bottom row, count the candidate bodies since it, and say whether
the number has passed twenty five. That is a parser over one table plus the `git log` the recipe
already runs, and it would need a home, since a gate under `scripts/` carries the full weight and
this one blocks nothing.

**What the shape would probably be.** It should not be a `just check` scan, which would fail a
commit for a condition no commit caused. Either a line in `just replay` with no argument, reporting the standing
count off the ledger rather than waiting to be asked with a date, or the ledger row becoming
machine readable enough for a scan that only ever warns. The first is a few lines and needs no new
module; the second is the one that could be read by something other than a person.

## Trail

- 2026-09-07: not fired, and the prediction the clause carried was wrong.
  `just replay "" 2026-08-25` reports nine candidate bodies since the ledger's last row, thirteen
  days after it, so no pass is due at all, let alone two windows of them. The prediction came from
  the burst the cadence addendum measured, thirty nine bodies in the four days after the
  2026-08-21 pass, and that rate did not hold: the sessions since have landed mostly documentation
  closes, which the recipe's vocabulary does not match. The trigger now names the number it was
  always about, fifty, and names the command that answers it, so the next reader compares against a
  measurement rather than an expectation. The nine is the first standing count this entry has, and
  it is evidence for the entry rather than against it, since it took a person running the recipe by
  hand to produce a number nothing else was keeping.
- 2026-09-10: still not fired, and the standing count has grown by six.
  `just replay "" 2026-08-25` reports fifteen candidate bodies since the ledger's last row,
  sixteen days after it, against a cadence of twenty five and a trigger of fifty. The rate over
  the nine days since the last reading is under one candidate body a day, so the entry's own
  evidence keeps accumulating in the same direction: the count is easy to produce and nothing
  produces it unless a person runs the recipe.
- 2026-09-12: landed, as the first of the two shapes this file proposed. `just replay` with no date
  now prints one line ahead of the draw: the date on the ledger's last dated row, the candidate
  bodies since it, the cadence, and whether the count has reached it. Today's reading is 21 since
  the pass of 2026-08-25, which is what the dated arm counts too, against a cadence of 25. The
  threshold is the recipe's own `window` default rather than a new one, the cadence and the draw
  window being one number in two roles, so the line adds no fifth copy of a number
  [R-440](440-the-replay-sample-is-spelled-in-three-places.md) is already about. What closes is the
  asking: the count no longer waits for somebody to hold the ledger's date and the command at the
  same time. Running a pass still starts with a person, which this file's own text declines to
  change, a workflow scheduling only the reminder keeping the calendar the cadence rejected. Two
  residues filed, the ledger's last row being trusted for its format and its order
  ([R-645](645-the-standing-count-takes-the-last-dated-row.md)) and the count reaching back to
  midnight of the pass's own day, which puts two of today's 21 inside the pass that drew them
  ([R-646](646-the-standing-count-includes-the-pass-day.md)). The four arms the line was measured
  over are in the [ADR-0002 standing-count addendum](../../adr/ADR-0002-toolchain-gates.md).
