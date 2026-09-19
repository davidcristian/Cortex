# A rewritten history no longer reproduces a recorded draw

**Status:** done 2026-09-19
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

The mutation-replay draw keys each candidate on a digest of the seed and the commit hash, so the
sample is a function of the hashes in the pool. This repo has rewritten the history covering
2026-08-25 since that pass ran, so every hash in the pool moved, and seed 19269061 at the recorded
tip now draws five bodies of which none is in the three tables the row says were replayed.

The ledger row's job is to say a pass happened, what it covered and what it found, and it still does
all three: the date, the window, the row counts and the result are unaffected by a rewrite, and so
is the replay count, whose anchor is a position in history rather than a draw. What a rewrite costs
is the ability to re-run one recorded pass's exact sample, which nothing in the practice asks for. A
replay pass draws fresh.

**What closed it.** The documentation says what is true. The runbook called the sample a function of
the seed alone and `just replay <seed>` the same five on any machine, the recipe's comment said the
same, and its reproduce line printed the seed alone. The five depend on the commits the window holds
as well, so a later HEAD can change them without any rewrite. The runbook now says a recorded seed
reproduces its draw on a checkout of the row's "Drawn from" commit and only until a rewrite moves
the hashes under it, and the reproduce line prints the commit beside the seed. The alternative, a
ledger cell naming the five bodies by subject, which survives a rewrite because a rewrite here keeps
subjects, was not built: no pass re-runs a recorded pass's exact sample, and it is one more
hand-written cell per pass.

## History

- 2026-09-15: opened by the close of
  [R-646](646-the-standing-count-includes-the-pass-day.md), which added the commit a pass drew from
  to the ledger. Filling that column for the pass of 2026-08-25 showed the problem had already
  happened for that row.
- 2026-09-19: done, as the documentation fix. The trigger could not wait for anything: it was
  already true when the entry was written. Seed 19269061 drew the same five at HEAD and twenty
  commits below it, and a disjoint five at `2712a6aa`. The origin record, ADR-0002 decision 20, has
  the reasoning.
