# A red gate run that named no tree

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)
**Trigger:** the next red whose failing tree is actually captured, or a third that is not, the first giving a pass something to reproduce and the second making the rate worth measuring on its own.

**What was observed.** Twice on 2026-08-17, `just check` run by the pre-commit hook exited 1 on a
tree that passed on both sides of it with nothing changed in between. The first was on the commit
that taught the backlog grammar to read a field's whole value when it wraps: four passing runs of
the same gate on the same tree around it, one failure. The second was on the commit that widened the
anchor check, where the sequence is exact and worth writing down, since the tree was fully staged
and therefore byte for byte identical across it: a manual `just check` exited 0, the hook's run of
the same recipe exited 1, and an immediate retry of the identical commit exited 0 and landed. Both
failures were single, both were bracketed by passing runs, and neither is explained.

**It did not reproduce.** After the second red, the gate was run twice more over the same tree with
the whole output kept, and both passed in 129 and 125 seconds. Two runs are not a rate, and two
passes are the outcome a genuinely intermittent failure gives most of the time, so this narrows
nothing. It does say the failure is not a standing property of that tree.

**What was not established**, and this is most of the entry. Which of the four trees failed.
Which check inside it. Whether the failure is order dependent, load dependent, or an environment
hiccup that has nothing to do with the tests. Whether the two occurrences share a cause at all, or
whether counting them together is already an assumption. Nothing was retained from either run.

**Why nothing was retained is not a property of the gate.** `just check` buffers each tree's output
and prints `=== check-<tree>: OK|FAILED ===` ahead of it, so the failing tree is named in the log
both times. Pre-commit surfaces a hook's output only when the hook fails, and on both occasions the
caller kept only the tail of that output. The tail is the overlay's coverage table, which prints
last whichever tree failed, so it identifies nothing. The remedy costs nothing and is procedural:
capture the whole of a failing hook run, never a tail of it. What a captured failure looks like
turned up by accident during the two re-runs above: a third and fourth run failed in about a second
each, and their logs named the recipe, the tree and the reason on one line, because this file had
been written between runs and the index was stale. That failure is explained and is not this one. It
is what the other two would have looked like had anything been kept.

**A hypothesis, offered as one.** Every suite here now runs shuffled, and every seed is fixed, so
for a given checkout an order is a pure function of its seed and an order-dependent failure ought to
reproduce on the re-run that a person does first. Two things weaken that reasoning rather than
supporting it. libtest hands its shuffled list to parallel workers, so a pair of tests inside one
thread window races whichever way it was drawn, which the shuffle decision already records as a
population the shuffle is worth nothing for. And the four trees run in parallel under one `just
check`, so the load each sees differs run to run in a way no seed fixes, and anything timing
sensitive underneath moves with it. Neither of those was measured here. They are the first two
places to look, not findings.

**What would close it.** Nothing to build, which is why this waits. The next failure has to be kept:
run the gate with its whole output captured, read the `FAILED` marker to get the tree, and take the
seed the failing suite printed in its own header. A failure that names its tree and its seed is a
bug report somebody can act on; one that names neither is this entry, and a third of those would say
only that the rate is not negligible.

## Trail

- 2026-08-17: written down after the second occurrence, on the pass that widened the anchor check to
  every document in the repo. Recorded rather than diagnosed: two failures, no tree named for
  either, a passing re-run of the identical tree after each, and two further passing runs that
  narrowed nothing.
