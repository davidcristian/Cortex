# The raw arm every envelope reading is measured against is held to no floor

**Status:** open, actionable
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
