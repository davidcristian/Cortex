# Two of the subagent row's five entries have been asked what the reply envelope costs them

**Status:** open, actionable
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
