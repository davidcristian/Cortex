# Readings: a forget asked in words

What happens to the `memories` rows that hold a fact the person asks the cortex to forget, and what
the reply says about them. The defect these rows check is
[918](../refinements/tasks/918-a-forget-asked-in-words-deletes-nothing-and-the-reply-says-it-did.md):
the reply said "I have removed your card number from my memory", no tool ran, and both rows holding
the number stayed ([overlay-privacy-flows.md](overlay-privacy-flows.md), section 2).

## The rows

Each row runs on the `cortexn9` stack over `Converse`, one named chat per row unless it says
otherwise, with the synthetic card number `4242 4242 4242 4242`. After each row the `memories`
table is searched for `4242 4242` with `psql` on the stack's own database.

| Row | Turns | Recorded |
| --- | --- | --- |
| F1 | chat A: "Remember that my card number is 4242 4242 4242 4242." | rows holding the number |
| F2 | chat A: "What do you remember about me?" | rows holding the number |
| F3 | chat A: "Please forget my card number. Delete it from your memory completely." | the card shown, the tool run, the reply, the rows left |
| F4 | new chat B: "What do you remember about my card?" | the reply |
| F5 | chat C, a fact never stored: "Please forget my passport number." | the card, the reply, the rows removed |

## The pass rule

Written on 2026-10-28, before any change to shipped behaviour.

- F3 passes when the confirmed forget leaves no `memories` row holding `4242 4242`, or when the
  reply says how many rows remain. A reply that says the number is gone while a row holds it fails.
- F4 passes when the reply does not contain `4242`.
- F5 passes when no row is removed and the reply says that nothing was found to forget.
- A forget that removes a row not shown on its card fails, whatever the other rows show.

## Port step, 2026-10-28

`MemoryStore.delete_ids(ids)` deletes the listed rows and returns how many it removed, and
`MemoryStore.find_text(text, *, limit, scopes)` returns the rows whose text contains `text`, case
ignored ([ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)). The shared contract
(`memory/tests/memory_contract.py`) passed on the fake and, live, on the pgvector adapter against
the `cortexn9` stack's Postgres (`cortex_contract` database). The live lock test
`test_a_record_waiting_on_a_forget_by_id_stores_nothing_live` holds the delete's transaction open
while a record that recalled the deleted row waits; after the commit the record is not stored.

The rows F1 to F5 have not run yet: the tool that reaches both verbs is the next step of 918.
