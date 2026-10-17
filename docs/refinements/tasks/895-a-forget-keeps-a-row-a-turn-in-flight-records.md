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

A count of forgets checked in the insert is not enough under Postgres's default isolation. A
per-scope counter row that does not exist yet cannot be locked, and a record that commits while
the forget's `DELETE` runs is outside that statement's snapshot. Two `psql` sessions on the
`cortexn7` stack's `cortex_contract` database on 2026-10-17 showed both halves of the fix below:
a record holding a share lock on its recalled row made the forget's `DELETE` wait, that `DELETE`
then removed the recalled row but not the new one, and a second `DELETE` removed the new one;
with the `DELETE` holding the row first, the waiting record inserted nothing.

The fix needs no schema change and no clock:

1. `TaintLedger` keeps the ids of the tainted memories the turn recalled
   (`_render_memory_context` in `turn_context.py` sees each hit). `HandoffRecord` stores them
   beside its taint fields and `taint_ledger()` restores them, so a deep reply recorded after a
   model swap keeps them.
2. `MemoryStore.add(record, *, recalled=())` stores the record only while every id in
   `recalled` still exists, and returns whether it stored it. The pgvector adapter checks this in
   the insert's own statement: `INSERT ... SELECT ... WHERE (SELECT count(*) FROM (SELECT id FROM
   memories WHERE id = ANY($7) FOR SHARE) AS kept) = $8`, over distinct ids. `MemoryRecaller.record`
   and `record_exchange` pass the ledger's ids, and a record that was not stored is logged.
3. `delete_tainted` repeats its `DELETE` until a pass removes nothing and returns the sum. A pass
   that waited on a record's share lock does not see that record, and a later turn can recall
   the record before the next pass, so one extra pass is not always enough.
4. An untainted record has no recalled tainted ids, since recalling one taints the turn, so it is
   stored as today. A tainted record with no recalled tainted memory, whose taint came from the
   turn's own tool reads, is stored as today too: it holds nothing the forget removed.
5. Contract tests that the fake and the pgvector store both pass: a record whose recalled id is
   gone is not stored and `add` returns false; one whose recalled ids all exist is stored. The
   live run adds the two-session case above. Core tests on fakes: a forget between a turn's
   recall and its record leaves no tainted row, for a cortex turn and across a handoff. The test
   stores that implement `delete_tainted`, in `core/tests/test_memory.py` and the two
   orchestrator session tests, gain the new parameter.
6. Update `docs/modules/brain-memory.md`, `docs/modules/brain-core-memory.md` and ADR-0019
   decision 9 in place, then replay the reproduction above on a stack with
   `CORTEX_MEMORY_ON_TAINTED=record`.

## History

- 2026-10-17: filed by the concurrency flows on the Linux shell.
