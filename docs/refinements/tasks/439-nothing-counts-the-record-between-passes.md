# Nothing counts the record between replay passes

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** a replay pass that turns out to have been due for two windows or more, which is what the ledger's dates will show the first time somebody looks.

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
already runs, and it would want a home, since a gate under `scripts/` carries the full weight and
this one blocks nothing.

**What the shape would probably be.** Not a `just check` scan, which would fail a commit for a
condition no commit caused. Either a line in `just replay` with no argument, reporting the standing
count off the ledger rather than waiting to be asked with a date, or the ledger row becoming
machine readable enough for a scan that only ever warns. The first is a few lines and needs no new
module; the second is the one that could be read by something other than a person.
