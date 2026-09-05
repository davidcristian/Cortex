# The text arm scores an empty or capped reply as resistance

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-09-05 by the close of
[R-547](547-the-pairs-budget-half-has-no-injection-row-of-its-own.md), which gave the injection
harness a row on which a Qwen entry is expected to return nothing.

Every detector in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
reads `content`, so a reply that is empty or was cut at the cap while the model was still
thinking is scored as resistance on all ten attacks. The image arm collects those replies as
`unusable` and fails the row on any, since a perfect score read off nothing is a measurement of
nothing. The text arm prints the same count beside each matrix since 2026-09-05 and asserts
nothing on it, so a `budget-alone` row on a Qwen entry, which the ADR-0005 budget-alone addendum
measured deliberating to the cap on 40 draws of 40, reads as 0 of 10 with the void reported one
line below.

**Why it was left.** The text arm's published rows were never held to it, and two of the deep
candidates are recorded in the GPU runbook returning exactly such replies, so an assertion would
fail rows that are read today by the runbook's rule rather than by a gate. Changing what a row
fails on was outside a close whose subject was which rows exist.

**What would close it.** The image arm's assertion applied to the text arm, `assert not unusable`
after the matrix is printed, with the deep candidates' rows either kept out of it or re-drawn under
a budget that answers, and the two published rows that would fail it re-read.

## Trail

- 2026-09-05: opened by the close of
  [R-547](547-the-pairs-budget-half-has-no-injection-row-of-its-own.md), which added the printed
  count and not the assertion.
