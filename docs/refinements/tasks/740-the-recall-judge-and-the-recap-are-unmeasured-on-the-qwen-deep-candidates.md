# The recall judge and the recap are unmeasured on the Qwen deep candidates

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-26

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

## History

- 2026-09-26: filed by the deep candidates' measurement.
