# A changed fact can be answered with its older value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-10-26

A person told the assistant a fact and later changed it, each statement in its own chat, and then
asked for it in a new chat. In two of five flows the answer named an older value
([readings](../../readings/overlay-memory-over-time-flows.md#one-value-replaced-twice)). Once the
`judge` recall rank kept only the oldest of three near-identical exchanges. Once the rank kept both
values, the newer first and worded as a rename ("I renamed my cat, she is called Pip now"), and the
reply still named the older. The rank's numbered notes (`build_rank_messages` in
`rerank_judge.py`) and the reply's memory list (`_render_memory_context` in `turn_context.py`) are
each memory's text alone, so nothing but the words tells either model which value is newer, though
every `MemoryRecord` has its `at`.

## Reproduction

On the shared stack with the default global scope and `judge` rank, in three new chats: "Please
remember this: my dentist appointment is on Tuesday.", then Thursday, then Friday. Then "Which day
is my dentist appointment? One word." in a fourth. With `CORTEX_MEMORY_RECALL_AUDIT=1` the
question's `cortex.memory.recall` line shows which ids were kept; join them on the `memories` table.

## What to do

1. Write rows and a pass rule first in the readings: several facts each changed two or three times,
   the question asked in a new chat, pass when the answer names the newest value. Run them on the
   current build for a baseline.
2. Show each recalled memory's date in both lists, the rank's notes and the reply's memory context,
   so the models can order the values. Measure the same rows again. Compare with `reranked`
   (similarity blended with recency), which orders by age without the model.
3. Ship the change only if the rows pass more often than the baseline, and record both in the
   readings.

## History

- 2026-10-26: filed from the memory over time flows on the Linux shell, where two of five
  answers named an older value. The same flows fired the trigger of
  [R-087](087-tiered-self-editing-memory.md).
