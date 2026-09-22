# Two of the subagent row's five entries have never been asked what the reply envelope costs them

**Status:** done 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

The subagent row of [ADR-0004](../../adr/ADR-0004-model-lineup.md) names five entries. Three had
been through the constrained reply path at 288 runs each, the default gemma-4-E4B, the roster
alternate Qwen3.5-2B and gemma-4-E2B. Two had not: Qwen3.5-0.8B (Q8_0/BF16) and Qwen3.5-4B
(Q4_K_M).

The reason to expect a real answer is that the three measured picks disagreed in every way they
could. One narrates without the sentence at three draws in four and one at one draw in sixteen; one
gains from the sentence overall and one loses; one writes into the reasoning channel on 14 draws of
96 and one on none of 288; and their failures are not even the same kind. The prediction written
down before the measurement: both remaining entries are Qwen, whose template renders the thinking
kwarg as a thought already closed, which on the three measured picks predicted the reasoning
residue exactly, so both should show a residue near zero. That prediction says nothing about the
answer rate.

## History

- 2026-08-28: opened by the close of
  [R-481](481-the-sentence-is-measured-on-one-pick.md), which measured the two picks a real
  deployment runs and stopped there against a clock.
- 2026-08-28: closed. Qwen3.5-0.8B Q8_0 and Qwen3.5-4B Q4_K_M were asked the same question through
  the same committed harness, the same four bodies, the same three subtask shapes, the same eight
  draws and the same `-ngl 99` substitution, 288 runs each, 576 in all, on llama.cpp
  `b10644-d7a207411`. The row is now measured whole at 1440 runs. The prediction held on both picks
  and every cell: both write into the reasoning channel on 0 draws of 288, and neither loses a shape
  to it. That is 0 of 864 across the Qwen entries against 22 of 192 across the two gemma-4-E
  entries, and the ADR-0005 template column has now predicted the residue on five entries out of
  five. The half the prediction could not reach is where the result is: the two picks are 28 draws
  apart on the shipped constrained path. Qwen3.5-4B answers 94 of 96, and its bare envelope costs it
  nothing measurable against its own unconstrained runs, 91 against 92, the first entry measured
  where the envelope is free. Qwen3.5-0.8B answers 66 of 96 against the bare envelope's 70, so the
  sentence is a cost on a second entry, and its extraction cell is 12 of 32, the worst measured
  anywhere here. The failure kind is a family property: 26 of the 0.8B's 30 constrained
  non-deliveries come back `ok=True`, and every cap refusal on both picks is the numeric runaway the
  roster alternate showed, never a lost trace. One reading is about the instrument: the `raw`
  control, 96 of 96 on all three earlier picks, answered 93 and 92 of 96 here, both times because
  the entry failed the subtask, and nothing in the harness compares it with anything. The `-ngl 99`
  substitution was also re-controlled on this family for the first time: 24 more runs of the 0.8B at
  `-ngl 0` on the summarization shape deliver 8 of 8, 7 of 8 and 8 of 8 against the card's 32 of 32,
  26 of 32 and 28 of 32, with no trace on either placement, at 10.4 to 17.3 tok/s against 91 to 350.
  The readings are the five-pick envelope review of 2026-08-28 at
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md), with the selection consequence at
  [ADR-0004](../../adr/ADR-0004-model-lineup.md), the engine half at
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section and the operator half in the
  subagent runbook. Opened by it:
  [R-484](484-the-control-run-has-no-minimum.md) and
  [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md).
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md) is amended rather than reopened.
