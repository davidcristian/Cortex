# A forget keeps a row a turn in flight records

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 9
**Verified:** 2026-10-17

`forget_untrusted_memories` deletes the tainted rows that exist when it runs. A turn in another
chat that recalled one of those rows before the delete still answers from it, which is allowed,
and then `record_exchange` stores its own exchange as a new tainted row after the delete. That row
holds the forgotten fact, so the next chat recalls it although the person was told it was
forgotten. Decision 9 already declines to record the forgetting turn itself for this reason; a
turn running beside it is not covered.

Reproduction ([readings](../../readings/overlay-concurrency-flows.md)), with
`CORTEX_MEMORY_ON_TAINTED=record` and a file `shed.txt` holding "The shed's padlock code is
4417." in the file sidecar's root:

1. Chat A: "Read the file shed.txt and tell me what it says." One tainted row is stored.
2. Chat B: "Forget every remembered exchange that came from untrusted content.", approved; 0.3 s
   later chat C: "What is the shed's padlock code?". The forget deletes the row, C answers
   "4417", and a tainted row of C's exchange is stored 4.6 s after the delete.
3. A new chat D: "What is the shed's padlock code?" answers "4417".

## What to do

1. Keep a forget count per memory scope in the memory store, raised in the same transaction as
   `delete_tainted`.
2. A turn reads the counts of its read scopes when it recalls, and a tainted exchange is inserted
   only while those counts are unchanged, checked in the insert's own statement so no forget can
   run between the check and the write.
3. Contract-test it on the fake and the pgvector store: a forget between a recall and the record
   drops the tainted record; an untainted record and a turn with no forget are stored as today.

## History

- 2026-10-17: filed by the concurrency flows on the Linux shell.
