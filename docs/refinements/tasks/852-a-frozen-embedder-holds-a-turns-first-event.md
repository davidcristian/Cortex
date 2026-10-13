# A frozen embedder holds a turn's first event for 30 s

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-13

With the embedding server frozen (`docker pause`), a turn sends nothing for 30.0 s: the recall's
embedding waits out the httpx timeout `_EMBEDDER_TIMEOUT_S` (30 s, `memory_builders.py`) before the
`forgoing` status appears and inference starts
([readings](../../readings/store-and-sidecar-outages.md#the-embedding-server)). The person sees only
the pending bubble. The write after the reply is bounded at `MEMORY_WRITE_TIMEOUT_S` (10 s) in the
core, and the slowest exchange embedding measured with every core busy took under a tenth of 30 s.

## Reproduce

On the GPU stack, `docker pause` the `llama-embed` container, send any turn over `Converse`, and
time the first event; `docker unpause` after.

## What to do

Decide the recall's bound on the same measurement as the write's: a shorter embedder timeout in
`memory_builders.py`, or a bound on the recall in `turn_context._recalled_context` that leaves the
`judge` recall policy, which asks a model, its own time.

## History

- 2026-10-13: filed when the memory write was bounded at 10 s; the recall keeps the embedder's
  30 s.
