# The recall judge and the recap are unmeasured on the Qwen deep candidates

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-28

During a handoff the deep model answers two calls besides the reply: the recall judge, which ranks
the recalled notes under `ORDER_ENVELOPE` with thinking off and no trace, and the history recap, also
with thinking off ([ranked recall](../../readings/ranked-recall.md)). Both were drawn on the deep
pick on 2026-09-24, where every MRR and `ABSENT` count equalled the cortex's and no recall fell
back. Neither has been drawn on Qwen3.8-27B or on the alternate Qwen3.6-27B.

Two things make the pick's reading a poor guide for them. The tier's request sends no sampler
field, so a Qwen deep tier answers these calls at the engine's sampler with the thinking-mode
values its GGUF sets (temperature 1.0, top_k 20, top_p 0.95), where the model cards give
temperature 0.7, top_p 0.80 and presence 1.5 for thinking off. And with thinking off the Qwen
template closes an empty thought in the prompt, a shape the switch probe drew only at a 256-token
cap ([thinking switch](../../readings/thinking-switch.md)).

What would close it: `test_rerank_judge_live.py` and `test_history_recap_live.py` against each
served at the deep tier's argv, about five card minutes each after the load, published beside the
pick's rows in the ranked-recall record.

**Written 2026-09-28, before the draw.** Each candidate is served on the card by the injection
harness's `_server` at the deep tier's argv, with the CPU embedder beside it, as the pick's row was,
in the unattended run logged at `measurements/sitting-2026-09-28/` (`740q38.log`, `740q36.log`). A
row draws `test_rerank_judge_wide_live.py` once over its 26 questions, then
`test_history_recap_live.py::test_the_recap_is_measured_against_the_window_that_ships` three times,
since at the engine's sampler one recap is one sample. No sampler field is sent, as the tier sends
none.

Deciding: the judge's correct count, the gold first on the 22 answerable questions plus an empty
return on the 4 `ABSENT` ones, a fallback counting as a miss, of 26, against the pick's 26 by a
two-sided Fisher test, apart at p below 0.05, which is 20 or fewer. A candidate apart below files a
task to send the thinking-off sampler values on the judge's request; if neither is apart, the rows
are published beside the pick's and this entry closes. The recap test passes when the recapped
answer keeps the fact the shipped window lost; a candidate that passes it in fewer than 2 of 3 files
the same task for the recap's request, and the pick's single pass decides nothing against it.
Predicted: Qwen3.8-27B 25 of 26 (22 to 26) and 3 recaps of 3; Qwen3.6-27B 24 of 26 (20 to 26) and 3
of 3 (2 to 3); neither apart. Priced at 900 s and 1200 s with the loads.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-28: premise checked against `judge_row.py` in `measurements/sitting2-2026-09-24/`, which
  drew the pick's row and takes any brain candidate by label; the rule and the predictions are
  written above before the draw.
