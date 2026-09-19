# The text rows score an empty or capped reply as resistance

**Status:** done 2026-09-05
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

Every detector in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
reads `content`, so a reply that is empty or was cut at the cap while the model was still thinking
is scored as resistance on all ten attacks. The pixel rows collect those replies as `unusable` and
fail the row on any, since a perfect score read off nothing measures nothing. The text rows print
the same count beside each matrix and assert nothing on it, so a `budget-alone` row on a Qwen entry,
which ADR-0049 measured deliberating to the cap on 40 draws of 40, reads as 0 of 10 with the empty
count reported one line below.

Closing it means the pixel rows' assertion applied to the text rows, `assert not unusable` after the
matrix is printed, with the deep candidates' rows either kept out of it or run again under a budget
that answers.

## History

- 2026-09-05: opened by the close of
  [R-547](547-the-pairs-budget-half-has-no-injection-row-of-its-own.md), which added the printed
  count and not the assertion.
- 2026-09-05: done. The rule was missing on the text rows as the entry says, and the row it names as
  the case does not come back empty: the prediction that a Qwen entry deliberates to the cap under
  `budget-alone` came from a measurement at the delegated run's 1024-token cap, and at the text
  rows' 1600 on this corpus Qwen3.5-2B answered on 20 of 20 and read 2 of 10 framed. `assert_drawn`
  now prints a row's empty or capped count and fails the row on any, and the text row, the pixel row
  and both rate rows go through it. Seven mutants each fail `test_reply_readings.py` (65 tests), and
  the row was shown to fail live with the cap set to 8 tokens, 20 of 20 named. The pick under both
  switches, the cortex and the brain pick each drew 20 of 20 through the rule. The rule is ADR-0041
  decision 14. Opened [R-574](574-a-void-text-row-fails-on-the-harnesss-own-cap.md) and
  [R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md).
