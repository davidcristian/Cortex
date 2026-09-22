# A failing check run that named no tree

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Trigger:** the next failing `just check` whose whole output is kept, which names its tree in a `=== check-<tree>: FAILED ===` marker and its seed in the failing suite's own header, that being the one form of this failure a later pass can reproduce from.
**Verified:** 2026-09-19

Twice on 2026-08-17, `just check` run by the pre-commit hook exited 1 on a tree that passed on both
sides of it with nothing changed in between. The first was on the commit that taught the backlog
grammar to read a field's whole value when it wraps: four passing runs of the same command on the
same tree around it, one failure. The second was on the commit that widened the anchor check, where
the tree was fully staged and therefore identical across the sequence: a manual `just check` exited
0, the hook's run of the same recipe exited 1, and an immediate retry of the identical commit
exited 0. Both failures were single, both were bracketed by passing runs, and neither is explained.

It did not reproduce. After the second failure the command was run twice more over the same tree
with the whole output kept, and both passed, in 129 and 125 seconds. Two passes are the outcome a
genuinely intermittent failure gives most of the time, so that narrows nothing beyond saying the
failure is not a permanent property of that tree.

What was not established is most of this entry: which of the four trees failed, which check inside
it, whether the failure is order dependent, load dependent or an environment problem, and whether
the two occurrences share a cause at all. Nothing was kept from either run.

The reason nothing was kept is not a property of the check. `just check` buffers each tree's output
and prints `=== check-<tree>: OK|FAILED ===` ahead of it, so the failing tree was named in the log
both times. Pre-commit shows a hook's output only when the hook fails, and on both occasions the
caller kept only the tail of that output, which is the overlay's coverage table and identifies
nothing. The remedy is procedural and costs nothing: keep the whole of a failing hook run.

One hypothesis, offered as one. Every suite runs shuffled under a fixed seed, so for a given
checkout an order is a function of its seed and an order-dependent failure ought to reproduce.
Two things weaken that. libtest hands its shuffled list to parallel workers, so a pair of tests
inside one thread window races whichever way it was drawn. And the four trees run in parallel under
one `just check`, so the load each sees differs run to run in a way no seed fixes. Neither was
measured; they are the first two places to look.

## History

- 2026-08-17: Written down after the second occurrence: two failures, no tree named for either, a
  passing re-run of the identical tree after each, and two further passing runs.
- 2026-09-06: Checked, not triggered, and one half of the trigger was uncountable as written. No
  third occurrence is recorded, and the only other file describing an intermittent failure is
  [R-115](115-stop-bounds-deadline-check.md), which is about a deadline assertion. "A third that is
  not captured" cannot be answered from inside the tree, since an uncaptured failure is one that
  left no artifact, and there is no second place to count them, because the pre-commit hook is the
  only thing that runs this check on any schedule and CI has recorded no run at all
  ([R-594](594-no-workflow-in-this-repository-has-ever-run.md)). The trigger now names only the
  capture.
- 2026-09-11: Checked, not triggered. No failing run has been kept since. `just check` still runs
  the four trees in parallel, buffers each, and prints `=== check-<tree>: OK|FAILED ===` ahead of
  every log, and every suite still runs shuffled under a fixed seed it prints in its own header:
  9973 for the brain, 7919 for the scripts tree, 104729 for the body's coverage run and 65537 for
  the overlay.
- 2026-09-14: Checked, not triggered. No file dated 2026-09-12 or later describes a failing run,
  and the four fixed seeds are where they were: 9973 in `brain/pyproject.toml`, 7919 in
  `scripts/pyproject.toml`, 104729 on the body's coverage run in the justfile, and 65537 in
  `body/app/vite.config.ts`.
- 2026-09-19: Checked, not triggered. A search of the 148 files changed since 2026-09-14 for an
  intermittent or `FAILED` run finds only mutation-table rows and the brain handoff record's
  failed-reason decision, none of them about `just check`. The `check` recipe still prints `===
  check-$tree: $status ===` ahead of each buffered log, and the four seeds are unchanged.
