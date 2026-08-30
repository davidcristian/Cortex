# The raw arm every envelope reading is measured against is held to no floor

**Status:** landed 2026-08-30
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which measured the last two entries of the
subagent row and found the instrument's own control arm slipping on both of them.

`brain/packages/orchestrator/tests/test_envelope_cost_live.py` reads every envelope arm against
`raw`, the unconstrained shape with no schema and no appended sentence, and that is what makes a
number like "the envelope costs 24 of 96 answers" mean anything: the same pick over the same bodies
answers them all without it. On the first three entries of the row `raw` returned **96 of 96** every
time, and the record grew a habit of quoting it as a constant rather than as a reading.

It is not a constant. Qwen3.5-0.8B answered 93 of 96 unconstrained and Qwen3.5-4B 92 of 96, and both
losses are the entry failing the subtask rather than the envelope taking an answer away: a cap
runaway on an extraction, a lookup answered `Fortnite 18`. Nothing in the harness noticed. Its only
assertions are that every arm saw the same bodies in the same order and that every run reported
timings, so a pick whose raw arm collapsed to 40 of 96 would still produce a tidy table, and a
reader would price the envelope for a failure that belongs to the pick.

**What is wrong with the present shape.** The harness has no notion of a floor. The whole design is
paired, so the arithmetic is sound whatever `raw` does, but the *interpretation* is not: a delivered
rate is only attributable to the envelope while the unconstrained arm is near ceiling, and nothing
in the file, the sample it writes, or the addenda that read the sample states the condition it needs.

**What would close it.** A floor the harness itself carries, argued rather than picked: the run
asserts, or at minimum records and prints, the raw arm's delivered rate per shape and says plainly
that a cell below the floor prices the pick and not the envelope. That needs the judging the addenda
do by hand to move into the harness, which is the real cost here and is worth weighing against
leaving the floor as a sentence in the module docstring that a reader has to honour. Either is
better than the present silence, and the cheap half of it is one line in the docstring naming the
condition every published rate rests on.

## Trail

- 2026-08-28: opened by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which found the raw arm at 93 and 92 of
  96 on the two entries it measured, after three entries at 96 of 96 had made it look like a
  constant.
- 2026-08-30: Landed, as a refusal to publish rather than as an assertion inside the run. The
  premise was re-derived first and held whole: the driver still asserts only that the arms saw the
  same bodies and that every run reported timings, and no line of it reads `ok`, a stop reason or a
  word of a reply. The driver now records two more facts per run, the instruction the arm really
  put on the wire and whether the arm is the control, and the new `scripts/envelopefloor.py` turns
  those records into rates: it reports the control arm **per subtask shape** with the same Wilson
  95% interval the tables publish, and prints the comparison between the arms only while that
  control still stands. The floor is **nine tenths of a cell's own runs**, argued from this row
  rather than drawn from a sweep (its envelope arms have measured as low as 66 of 96, so a control
  under nine tenths is doing no better than the arms it explains), and the rule is **one-sided**,
  refusing only when a cell's whole interval lies under the floor: 25 of 32 on a swept cell, 80 of
  96 pooled, and a four-run probe only once half of it has failed. What a run **stood** is deliberately weaker than what a
  reply **delivered**, being the runner's acceptance, a non-empty reply and a reply that is not the
  ask handed back, so it bounds the judged rate from above and a red is always honest.
  The reading is the [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) control-arm
  addendum, with the tool's contract in [repo-gates](../../modules/repo-gates.md) and the operator
  half in the subagent runbook. Twelve mutations of the new module were each red against its
  29-test suite; the table is in that addendum. **No sweep was re-run and no rate in the record
  moved**: every rate quoted is the row addendum's, re-read. The instrument itself was run against
  synthetic samples in the driver's own format and then twice against a live Qwen3.5-0.8B Q8_0 on
  CPU, once at a starved cap where its control arm was refused at 0 of 1 and once on the lookup
  shape where it published 4 of 4, both too small to be a reading about the pick and both there to
  show the driver writes a sample this reader can read.
  Opened by it: [R-507](507-the-floor-sees-only-the-failures-a-machine-can-name.md), the narration
  and the wrong answer this floor cannot see, which is the judging half the entry named as the real
  cost and which is still done by hand. The second live run demonstrated it unasked: three of its
  four standing control replies name a reporting period their body never states, so that cell's
  judged rate is 1 of 4 where the machine-read rate is 4 of 4.
