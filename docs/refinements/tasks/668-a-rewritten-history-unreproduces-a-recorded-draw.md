# A rewritten history unreproduces a recorded draw

**Status:** landed 2026-09-19
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Opened 2026-09-15 by the close of
[R-646](646-the-standing-count-includes-the-pass-day.md), which added the commit a pass drew from
to the ledger. Filling that column for the pass of 2026-08-25 showed the trigger has already fired
for that row. The draw keys each candidate on a digest of the seed and the commit hash, so the
sample is a function of the hashes in the pool; this repo has rewritten the history covering
2026-08-25 since that pass ran, every hash in the pool moved, and seed 19269061 at the recorded
tip now draws five bodies of which none carries the three tables the row says were replayed.

**Why it was left this way.** The ledger row's job is to say a pass happened, what it covered and
what it found, and it still does all three: the date, the window, the row counts and the result are
unaffected by a rewrite, and so is the standing count, whose anchor is a position in history rather
than a draw. What a rewrite costs is the ability to re-run one recorded pass's exact sample, which
nothing in the practice asks for. A replay pass draws fresh.

**What would close it.** The ledger row naming the bodies it drew, by subject rather than by hash,
which survives a rewrite because a rewrite here preserves subjects. That is one more hand-written
cell per pass and it makes the row long. The alternative is to say in the runbook that a recorded
seed reproduces a draw only until the history under it moves, which is true, costs nothing, and
answers the reader who wondered rather than the reader who needed the five.

## Trail

- 2026-09-15: opened by the close of
  [R-646](646-the-standing-count-includes-the-pass-day.md).
- 2026-09-19: landed as the second remedy. The trigger could not wait for anything: it was already
  true when the entry was written, the entry's own second paragraph being the report of it firing.
  What was still wrong was the documentation, and in more cases than a rewrite. The runbook
  called the sample a function of the seed alone and `just replay <seed>` the same five on any
  machine, the recipe's comment said the same, and its reproduce line printed the seed alone. The
  five depend on the commits the window holds as well, so a later HEAD can change them without any
  rewrite. The runbook now says a recorded seed reproduces its draw on a checkout of the row's
  "Drawn from" commit and only until a rewrite moves the hashes under it, and the reproduce line
  prints the commit beside the seed. Seed 19269061 drew the same five at HEAD and twenty commits
  below it, and a disjoint five at `2712a6aa`. The first remedy, a ledger cell naming the five by
  subject, is not built, because no pass re-runs a recorded pass's exact sample. The origin
  record's 2026-09-19 addendum carries the reasoning.
