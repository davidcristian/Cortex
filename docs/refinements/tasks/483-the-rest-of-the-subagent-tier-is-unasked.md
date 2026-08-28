# Two of the subagent row's five entries have been asked what the reply envelope costs them

**Status:** landed 2026-08-28
**Area:** subagents
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

Opened 2026-08-28 by the close of
[R-481](481-the-sentence-is-measured-on-one-pick.md), which measured the two picks a real deployment
runs and stopped there against a clock.

The subagent row of [ADR-0004](../../adr/ADR-0004-model-lineup.md) names five entries. Three have now
been through the constrained reply path at 288 runs each, the default gemma-4-E4B, the roster
alternate Qwen3.5-2B and gemma-4-E2B. **Two have not**: Qwen3.5-0.8B (Q8_0/BF16) and Qwen3.5-4B
(Q4_K_M). Neither is a shipped default and neither has ever been asked whether the envelope, the
sentence, or the pair of them costs it an answer.

The reason to expect an answer rather than a formality is that the three measured picks disagreed in
every way they could. One narrates without the sentence at three draws in four and one at one draw in
sixteen; one gains from the sentence overall and one loses; one writes into the reasoning channel on
14 draws of 96 and one on none of 288; and their failures are not even the same kind, a cap refusal
meaning a lost reasoning trace on two of them and a repetition runaway on the third. So a prediction
about the two remaining entries is a prediction and not a reading, and the whole point of
[R-481](481-the-sentence-is-measured-on-one-pick.md) was that the first such prediction was wrong.

**What is predicted, so the measurement can falsify something.** Both are Qwen entries whose template
answers the thinking kwarg by rendering a thought already closed (the ADR-0005 lineup section's
table), which on the three measured picks predicted the reasoning residue exactly. So both should
show a residue near zero and neither should lose a shape to that channel. What that prediction says
nothing about is the answer rate: the roster alternate is on the same side of that column and still
lost 20 of 96 bare draws to echoing the instruction back and to repetition runaways, which is a
failure mode the column does not reach.

**What would close it.** The same three arms over the same four bodies at the same eight draws on
each of the two entries, on the same engine digest at `-ngl 99`, judged the same way, with the trace
residue counted as a rate over draws and the failure kind split into quiet and refused. That is about
ten minutes of decoding a pick on the card plus a bring-up each, and the numbers go into the ADR-0028
lineup addendum's two tables beside the three already there. The 0.8B is the more interesting of the
two, being the smallest entry in the lineup and the one most likely to narrate under a grammar if
size were the variable, which the measured three say it is not.

Worth folding in if it is cheap when this runs: the `-ngl 99` substitution every one of these
measurements rests on is argued and controlled once, in the ADR-0005 answer addendum, on the default
pick. It has never been re-controlled on a Qwen entry, and a CPU arm of one shape at a couple of
draws would say whether offload is still only throughput on the other family.

## Trail

- 2026-08-28: opened by the close of
  [R-481](481-the-sentence-is-measured-on-one-pick.md), which measured the two picks a real
  deployment runs and stopped there against a clock.
- 2026-08-28: Landed. The last two entries of the subagent row were asked the same question through
  the same committed harness, the same four bodies, the same three subtask shapes, the same eight
  draws and the same `-ngl 99` substitution: **Qwen3.5-0.8B Q8_0** and **Qwen3.5-4B Q4_K_M**, 288
  runs each, **576 in all**, on llama.cpp `b10644-d7a207411`. The row is now measured whole at 1440
  runs. The reading is the
  [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md) row addendum, with the selection
  consequence at [ADR-0004](../../adr/ADR-0004-model-lineup.md), the engine half at
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section and the operator half in the
  subagent runbook.
  **The prediction this entry wrote down held, on both picks and on every cell.** Both entries write
  into the reasoning channel on **0 draws of 288**, on all three arms and all three shapes, and
  neither loses a shape to it. That is 0 of 864 across the Qwen entries of this row against 22 of 192
  across the two gemma-4-E entries, and the ADR-0005 template column has now predicted the residue on
  five entries out of five, every time before a token was decoded.
  **The half the entry said the prediction could not reach is where the result is.** The two picks
  sit in the same cell of that column and are 28 draws apart on the shipped constrained path.
  Qwen3.5-4B answers **94 of 96**, and its bare envelope costs it nothing measurable against its own
  unconstrained arm, 91 against 92, the first entry measured where the envelope is free.
  Qwen3.5-0.8B answers **66 of 96 against the bare envelope's 70**, so the sentence is a cost on a
  second entry, and its extraction cell is **12 of 32**, the worst measured anywhere in this arc.
  The failure kind is a family property and not a pick's, which is the trap this entry was told to
  watch for and which fired again in the other direction: **26 of the 0.8B's 30 constrained
  non-deliveries come back `ok=True`**, and every cap refusal on both picks is the numeric runaway
  the roster alternate showed, never a lost trace. The 4B's two constrained non-deliveries split one
  and one, too few to read as a rate. Of the three entries whose failures are numerous enough to
  characterise, the two that fail mostly silently are both Qwen entries.
  **One reading is about the instrument.** The `raw` control arm, 96 of 96 on all three earlier
  picks, answered 93 and 92 of 96 here, both times because the entry failed the subtask rather than
  because the envelope took an answer away. Nothing in the harness holds it to anything.
  The `-ngl 99` substitution this whole arc rests on was also re-controlled on this family for the
  first time, the fold-in this entry asked for if it was cheap: 24 more runs of the 0.8B at `-ngl 0`
  on the summarization shape deliver 8 of 8, 7 of 8 and 8 of 8 against the card's 32 of 32, 26 of 32
  and 28 of 32, with no trace on either placement, at 10.4 to 17.3 tok/s against 91 to 350. Recorded
  in the ADR-0005 answer addendum's CPU control.
  Opened by it: [R-484](484-the-control-arm-is-held-to-no-floor.md), the control arm held to no
  floor, and
  [R-485](485-a-roster-description-never-says-whether-the-entry-answers.md), the description the
  cortex picks a roster entry by. [R-482](482-the-sentence-is-one-wording-for-every-entry.md) is
  amended rather than reopened: the sentence now costs two entries of five rather than one, and the
  two sit on opposite sides of the template column.
