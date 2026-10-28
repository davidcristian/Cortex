# ADR-0075: A forget of chosen memories finds rows by text and deletes them by id

**Status:** Accepted (2026-10-28)

## Context

A person who asks the cortex to forget a fact ("Please forget my card number") is told it is gone,
while every `memories` row holding it stays and a later chat recalls it
([readings](../readings/overlay-privacy-flows.md#2-remember-forget-and-delete-the-chat)). The
`MemoryStore` port deletes only a whole scope (`delete_scope`, the session-delete cascade of
[ADR-0008](ADR-0008-memory-v1.md) decision 11) or every tainted row of some scopes
(`delete_tainted`, [ADR-0019](ADR-0019-tainted-memory-recording.md) decision 9). Neither removes the
rows that hold one fact, because a fact the person typed is an ordinary row in the `global` scope,
beside every other memory.

A forget that removes a chosen set of rows needs two things: a way to find the rows, and a delete
that removes exactly those rows and holds against a turn in flight. This record decides both.

## Decision

1. **`MemoryStore.delete_ids(ids) -> int` hard-deletes the listed rows and returns how many it
   removed.** It reaches a row in any scope, because the caller chose the row by its id. An id that
   is not stored is not an error and adds nothing to the count, so a row removed by another forget
   in between is counted once. An empty list removes nothing. Fake: `InMemoryMemoryStore`; the
   shared contract in `memory/tests/memory_contract.py` checks both implementations.
2. **The pgvector statement locks its rows in id order**:
   `DELETE FROM memories WHERE id IN (SELECT id FROM memories WHERE id = ANY($1::text[]) ORDER BY id
   FOR UPDATE)`, with the distinct ids sent sorted. `add` takes its share locks in the same order
   ([ADR-0008](ADR-0008-memory-v1.md) decision 11), so the two cannot deadlock, and a record that
   recalled a row this delete removed waits for the delete to commit and is then not stored. The
   live test `test_a_record_waiting_on_a_forget_by_id_stores_nothing_live` checks it.
3. **One pass, not a loop.** `delete_tainted` repeats until a pass removes nothing, because a
   record committed while it waited is tainted and so matches the next pass. A record committed
   before this delete took its locks has a new id, which is not in the list, so a second pass would
   find nothing. A caller that must know whether the fact is still held searches again after the
   delete; the tool that will call this verb reports what remains rather than claiming it is gone.
4. **`MemoryStore.find_text(text, *, limit, scopes=None)` finds the rows that hold a fact by a
   literal match**: the rows whose text contains `text`, case ignored, oldest first and then by
   id, at most `limit`. The pgvector statement is `strpos(lower(text), lower($1)) > 0` with the
   scope filter `search` uses. A literal match is checkable: a row holds the named text or it does
   not, so a card can say why each listed row was chosen. Both implementations lower case with
   their own rules, which agree on ASCII; that the database collation agrees with Python on other
   letters is an assumption no test checks.
5. **The built-in `forget_memories` (`ForgetChosenTool`) is the one caller.** It takes one `text`:
   the value when the model knows it, and otherwise one word from the request that names it, such
   as `passport`, because a model told to pass only the value asked the person to type it. A
   search that finds nothing returns a result saying there is nothing to forget and no need to
   ask for the value.
   Its confirmation card runs `find_text` over the session's read scopes and lists an excerpt of
   each matching row, so the card shows stored text and never text the model wrote; that is why
   the dispatcher may show it on a tainted turn. The tool keeps the ids it listed under the call's
   id, and `invoke` deletes exactly those, so a row written after the card was shown is never
   deleted unseen. The ids live in the brain process only between the card and the answer to it,
   the same span the dispatcher holds the call. After the delete it searches again and reports
   any row still matching, so the reply never claims a fact is gone while a row holds it.
6. **A card lists at most 20 rows.** More matches delete nothing and ask for a more exact text,
   so a short text such as one letter cannot clear the memory behind a card nobody reads.
   The pass rule is in [forget-chosen-memories.md](../readings/forget-chosen-memories.md).

## Consequences

- The port has a third delete. `delete_scope` and `delete_tainted` keep their callers and meaning.
- The ids reach Postgres as one bound `text[]`, so a list of any length is one statement and no id
  is ever written into the SQL text.
- A row that repeats a forgotten fact and was written by a turn that committed first survives the
  delete. Finding it is the search's job, not the delete's.
- A recall reply that repeats a stored fact is still recorded like any exchange. The text search
  reaches every copy, so a forget needs no rule about what a recall may record.
- `find_text` scans `memories` row by row, since no index serves a substring match; it runs only
  when a person asks for a forget, never on a turn's recall.

## Alternatives rejected

- **A similarity search for the rows to forget.** It ranks every row, so choosing which rows hold
  the fact needs a score floor, and no reading sets one for the shipped embedder.
- **Delete by a text match in the store.** A `DELETE ... WHERE text ILIKE` removes rows the person
  never saw on a card, which the pass rule fails; the card must list exactly what is deleted.
- **A taint-like marker on the rows to forget, then `delete_tainted`.** It reuses the loop, but it
  mixes two meanings in one column and lets a tainted forget remove rows the person chose to keep.

## Related

- [ADR-0008](ADR-0008-memory-v1.md): the memory store and its other deletes.
- [ADR-0019](ADR-0019-tainted-memory-recording.md): the tainted forget and its confirmation card.
- Module docs: [brain-core-memory.md](../modules/brain-core-memory.md),
  [brain-memory.md](../modules/brain-memory.md).
