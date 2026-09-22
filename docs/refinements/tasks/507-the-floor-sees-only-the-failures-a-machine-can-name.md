# The control minimum counts only the failures a machine can name

**Status:** done 2026-09-04
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

`scripts/envelopefloor.py` counts a run as having stood when the runner accepted it, the reply is
not empty, and the reply is not the instruction handed back. Those three are visible whatever was
asked, which is what lets the minimum apply to a harness whose subtask is a setting
(`CORTEX_ENVELOPE_INSTRUCTION`). What the published tables count instead is delivered, judged by
number recall against the body on a summarization and an extraction and by whether the reply names
the body's own reporting period on a lookup, with two decisions on top: a comma read once as a
thousands separator and once as a separator, and a strict reading that counts a run cut at the cap
as a non-delivery. That judging is done by hand, in a scratchpad, once per measurement.

So the two numbers are different, and the gap is exactly the failure this work is about. A reply
that narrates the subtask rather than doing it is well formed, accepted, non-empty and not an echo,
and it stands. On the shipped constrained path of the default pick, 23 of 24 bare non-deliveries
were `ok=True` narrations of that kind. The minimum is sound in the direction that matters, `stood`
bounding `delivered` from above so a refusal is always correct, and it does not see the other case:
a control could narrate every one of its 96 runs and clear it.

It was demonstrated on real replies the day it was built, by accident. A four-run probe of the
lookup shape on Qwen3.5-0.8B Q8_0, at a 256-token cap on CPU, published `stood on 4 of 4` for its
control. One of the four replies answers, `Week 34`. The other three say `week ending Wednesday,
July 29, 2024`, `the month of April` and `the second half of the month`, against bodies whose own
periods are `week 34` and `month ending`, so the judged rate of that cell is 1 of 4 where the
machine-read rate is 4 of 4.

## History

- 2026-08-30: opened by the close of
  [R-484](484-the-control-run-has-no-minimum.md), which built the minimum on the failures a
  reader can name without knowing the subtask and left the rest judged by hand.
- 2026-09-02: the close of
  [R-511](511-the-shipped-reasoning-off-pair-disarms-its-own-sampler.md) judged 320 replies by hand
  for exactly this reading, a narration or a plan where an answer belongs, because the flag
  combination it decided against loses answers that way and no other way: 11 of 40 with no reasoning
  character. The minimum would have counted 9 of those 11 as accepted.
- 2026-09-04: closed. The premise was checked first and held: `envelopefloor.py` read only the
  runner's result, an empty reply and an echoed request, the tables' `delivered` is judged by hand,
  and the phrase `number recall` appeared in exactly one file in the tree. One thing the entry did
  not say decided the shape: the driver recorded the instruction a run sent and not the report body,
  so nothing a reader could reach knew what a reply was supposed to recall.
  `scripts/envelopejudges.py` declares a judge per subtask shape beside the instruction it belongs
  to, matched on a run's opening so one declaration covers the runs with the appended sentence and
  the runs without it, and a shape nobody declared one for publishes `stood` alone and says so. The
  two decisions plus the lookup's own are stated columns, `--comma`, `--refusal` and `--naming`,
  printed at the top of every report. `scripts/envelopesamples.py` answers for the sample format and
  refuses a run with no body by name. `delivered` has its own minimum, applied to the control alone,
  whose delivery is the condition every other rate rests on, and the nine tenths was argued over
  delivered rates in the first place. Checked against the record, the new minimum refuses none of
  the five measured picks. Measured live on the shipped default pick at 72 runs, and the second run
  shows the gap: its bare variant stood 12 of 12 and delivered 6 of 12, every non-delivery `ok=True`
  and not an echo. Both columns were compared by hand across all 72 runs and agree 72 of 72, and the
  recall band from 0.07 to 0.53 that held 0 of 384 replies in the five-pick envelope review of
  2026-08-28 holds 0 of 56 here. Thirteen mutations of the three modules each failed against their
  53-test suite; the table is in
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decision 14, with the tool's
  contract in [repo-checks](../../modules/repo-checks.md) and the operator half in the subagent
  runbook. No measurement was re-run and no rate in the record moved. Opened by it:
  [R-540](540-the-judged-rate-and-hand-read-column-are-compared-on-one-probe.md) and
  [R-541](541-the-measured-subtask-instructions-are-written-in-two-trees.md).
