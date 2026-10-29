# A failed discard of a deleted chat's row fails the turn

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-29

`record_exchange` (`turn_output.py`) catches `EmbedderError`, `MemoryStoreError` and `TimeoutError`
around the memory write, logs that the exchange was not recorded, and returns, so a memory failure
never fails a turn whose reply is already shown and saved. The two calls added after it are outside
that handling: `store.deleted(session_id)` after the row commits, and `caps.memory.discard(stored)`
when the chat was deleted meanwhile. The discard also runs without `memory_write_timeout_s`.

Reproduced on 2026-10-29 with a unit probe over the fakes: a `MemoryStore` whose `add` stores the
row and then deletes the chat, and whose `delete_ids` raises `MemoryStoreError`. `handle_turn`
raised `MemoryStoreError('connection lost')` after the reply, with no `TurnCompleted`, so
`ConverseStream` ends the turn as `internal`, and the deleted chat's row stayed in the store. A
`SessionStoreError` from the second `deleted` read ends a shown reply as `session_store_unavailable`
the same way.

## What to do

1. Decide in ADR-0021 what a failed discard does: log it at error with the row's id and the chat's
   id and return, as every other memory failure there does, or keep the id somewhere a later delete
   or the next start removes it from. A brain stopping between the commit and the read already
   keeps the row, so the first matches the window the ADR accepts.
2. Put the discard under the write's timeout, and add the probe above as a test with the turn
   completing.

## History

- 2026-10-29: filed from the closing audit of the deleted chat marker.
