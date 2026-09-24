# The deep model's recall judge is unmeasured

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-24

The deep phase of a handoff runs inside the residency scope for the deep model, where no other
model can be leased, so `StreamEngines.for_stream`
([engines.py](../../../brain/packages/orchestrator/src/cortex_orchestrator/engines.py)) builds its
recall judge and its history recap over the deep model. No draw has asked the deep model either
request. The judge sends one rank request per escalated turn whose recall finds a candidate, with
thinking off, the `ORDER_ENVELOPE` schema and `rank_bounds(k)`
([rerank_judge.py](../../../brain/packages/core/src/cortex_core/rerank_judge.py)). The recap runs
only when the cortex turn stored none for the same boundary. Nothing records how often the deep
model's rank answer parses, or how long the request adds to a handoff at the tier's decode rate.

An answer that does not parse falls back to the unjudged ranking, and a recap with no usable text
falls back to the plain window, so a bad answer costs recall quality or time, never a stuck turn.

The measurement: escalated turns on the card over stored memories, recording the parse rate of the
deep model's rank answers and each request's wall clock beside `clocks.sm` against
`clocks.max.sm`, in a readings record.

**Pre-registered 2026-09-24.** The rank request and the recap are the same requests inside a handoff
as outside one, since the residency scope decides only which model answers. So the row asks the deep
model directly rather than through escalated turns. An unattended run logging to
`measurements/sitting2-2026-09-24/` draws it second, one process that starts the CPU embedder as
`docker-compose.memory.yml` does and serves gemma-4-31B through the injection harness's `_server` at
its GPU placement (every layer on the card, `--ctx-size 8192 --parallel 1`, server switch thinking
on; each rank and recap request sends thinking off through its bounds), then runs:

- `test_rerank_judge_wide_live.py`, one pass over `recall_corpus.py`: 26 questions over 41 notes, `k`
  3 over a pool of 12, one rank request per question;
- `test_history_recap_live.py::test_the_recap_is_measured_against_the_window_that_ships`, one fold.

The server's log is kept, so each request's prompt and decode time is read from its `eval time`
lines, beside `clocks.sm` against `clocks.max.sm`.

- **What decides** is the number of the 26 recalls that fell back. At 2 or fewer the deep model's
  rank answer is recorded as usable and this task closes with a readings entry in
  [ranked recall](../../readings/ranked-recall.md). At 3 or more a task is filed to change what the
  deep phase's judge sends. The recap part is one sample and decides nothing.
- **Predictions**, with a 90% range: fell back 0 (0 to 2); judge MRR over the 22 answerable 1.000
  (0.93 to 1.000); the four `ABSENT` questions return nothing 4 of 4 (2 to 4); a recall costs 1.5 s
  (0.7 to 4.0) at a median SM clock of 0.55 to 0.75 of the card's maximum; the fold stores an
  account, its cold pass costs 9 s (4 to 20), and the recapped answer has the fact.
- **Cost.** Estimated at 600 s and stopped at 1200 s: the model loaded in 96.5 s on 2026-09-24.

## History

- 2026-09-24: Opened by the change that has the deep phase's recall judge and history recap ask
  the deep model, the one model its residency scope can lease.
