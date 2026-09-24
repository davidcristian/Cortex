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

## History

- 2026-09-24: Opened by the change that has the deep phase's recall judge and history recap ask
  the deep model, the one model its residency scope can lease.
