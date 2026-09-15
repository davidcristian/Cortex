# A rewritten history unreproduces a recorded draw

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Verified:** 2026-09-15
**Trigger:** somebody tries to reproduce a ledger row's sample from its seed and its tip, and the
five bodies the draw returns are not the ones the row says were replayed.

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
