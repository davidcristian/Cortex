# A hung memory write holds the turn open

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-13

`Engine.handle_turn` in `engine.py` awaits `record_exchange` after the reply is stored and before
it yields `TurnCompleted`, so the turn ends only when the memory write ends. With the embedding
server frozen, a one sentence turn completed at 67.6 s: 30 s for the recall to time out, the
reply, then 30 s more for the write to time out, with the whole reply on screen and the composer
still showing the stop button
([readings](../../readings/store-and-sidecar-outages.md#the-embedding-server)). The write can only
log a failure (ADR-0008 decision 12), so the person waits for nothing.

## Reproduce

On the GPU stack, `docker pause` the `llama-embed` container, send any turn over `Converse`, and
time `turn_complete` against the last text delta; `docker unpause` after.

## What to do

Send `TurnCompleted` before the write, or bound the write well under the recall's bound. The deep
phase in `brain_phase.py` calls `record_exchange` the same way. Moving the write after the yield
needs it to outlive the stream that stops reading at `turn_complete`, which the one hard rule in
AGENTS.md allows only if nothing it needs lives in the process.

## History

- 2026-10-13: filed from the outage flows in
  [store-and-sidecar-outages.md](../../readings/store-and-sidecar-outages.md).
