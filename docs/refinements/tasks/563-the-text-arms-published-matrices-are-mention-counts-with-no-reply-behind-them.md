# The text arm's published matrices are mention counts with no reply behind them

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-05 by the close of
[R-543](543-the-description-confound-grows-with-the-image-budget.md), which gave the injection
harness a structural reading of each reply and re-read the pixel matrices on it.

Every text-arm number this repo has published, the lineup table in ADR-0004, the hardening rows in
ADR-0013, the switch, placement and budget-alone rows of 2026-09-04 and 2026-09-05, was counted on
the mention reading: the canary anywhere in the reply. The text arm never printed a reply, so none
of those cells can be re-read. The image-arm addendum's claim that the text arm "never had this
problem, because its benign document has content of its own to summarise" is an observation from
reading the cortex's replies in one sitting, and the `plain` rendering has content of its own too
and still described the rule at the shipped budget. On 2026-09-05 the subagent pick's control arm
fired `refusal-suppression` and `output-laundering` on the shipped switch, and nothing says whether
either was the token written or the file's instruction reported.

**Why it was left.** The close that opened this was about the pixel channel, where the confound
was measured, and its one live row was spent there. The text arm now scores and prints both
readings, so every row from here on carries both; what is missing is the rows already published.

**What would close it.** Run the thinking-off rows once with the harness as it stands, the five
subagent candidates on the shipped switch, the pick at both placements, and publish the obeyed
count beside each published mention count where that count is recorded, ADR-0004's lineup table
and ADR-0013's hardening addendum. Add any reply where the two readings disagree to `RECORDED` in
[test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py) with the
verdict it was given by hand. If every fired cell obeys, the published text numbers stand as
obedience counts and this closes as satisfied; if some describe, the text arm had the confound
too and the published numbers were high by that many.

## Trail

- 2026-09-05: opened by the close of
  [R-543](543-the-description-confound-grows-with-the-image-budget.md), which made both readings
  print on the text arm and re-read no text row.
