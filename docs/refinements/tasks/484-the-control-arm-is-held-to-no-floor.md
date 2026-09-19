# The control run every envelope reading is compared against has no minimum

**Status:** done 2026-08-30
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

`brain/packages/orchestrator/tests/test_envelope_cost_live.py` reads every envelope variant against
`raw`, the unconstrained shape with no schema and no appended sentence, and that is what makes a
number like "the envelope costs 24 of 96 answers" mean anything. On the first three entries of the
row `raw` returned 96 of 96 every time, and the record began quoting it as a constant rather than
as a reading.

It is not a constant. Qwen3.5-0.8B answered 93 of 96 unconstrained and Qwen3.5-4B 92 of 96, both
losses being the entry failing the subtask rather than the envelope taking an answer away: a cap
runaway on an extraction, a lookup answered `Fortnite 18`. Nothing in the harness reported it. Its
only assertions are that every variant saw the same bodies in the same order and that every run
reported timings, so a pick whose control collapsed to 40 of 96 would still produce a tidy table.
The arithmetic is sound whatever `raw` does, because the design is paired, but a delivered rate is
only attributable to the envelope while the unconstrained runs are near the top, and nothing states
that condition.

## History

- 2026-08-28: opened by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which found the control at 93 and 92 of
  96 on the two entries it measured, after three entries at 96 of 96 had made it look like a
  constant.
- 2026-08-30: closed, as a refusal to publish rather than as an assertion inside the run. The
  premise was checked first and held: the driver still asserts only that the variants saw the same
  bodies and that every run reported timings, and no line of it reads `ok`, a stop reason or a word
  of a reply. The driver now records two more facts per run, the instruction the variant really sent
  and whether it is the control, and the new `scripts/envelopefloor.py` turns those records into
  rates: it reports the control per subtask shape with the same Wilson 95% interval the tables
  publish, and prints the comparison between the variants only while that control still stands. The
  minimum is nine tenths of a cell's own runs, argued from this row rather than taken from a review
  (its envelope variants have measured as low as 66 of 96), and the rule is one-sided, refusing only
  when a cell's whole interval lies under it: 25 of 32 on a reviewed cell, 80 of 96 pooled, and a
  four-run probe only once half of it has failed. What a run stood is deliberately weaker than what
  a reply delivered, being the runner's acceptance, a non-empty reply and a reply that is not the
  request handed back, so it bounds the judged rate from above. The reading is
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) decision 13, with the tool's
  contract in [repo-checks](../../modules/repo-checks.md) and the operator half in the subagent
  runbook. Twelve mutations of the new module each failed against its 29-test suite; the table is in
  the commit that added it. No measurement was re-run and no rate in the record moved. The
  instrument itself was run against synthetic samples in the driver's own format and then twice
  against a live Qwen3.5-0.8B Q8_0 on CPU, once at a starved cap where its control was refused at 0
  of 1 and once on the lookup shape where it published 4 of 4. Opened by it:
  [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md): the second live run showed it
  unasked, three of its four accepted control replies naming a reporting period their body never
  states, so that cell's judged rate is 1 of 4 where the machine-read rate is 4 of 4.
