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
   search that finds nothing returns a result telling the model to say that nothing about it was
   stored and not to ask for the value.
   Its confirmation card runs `find_text` over the session's read scopes and lists an excerpt of
   each matching row, so the card shows stored text and never text the model wrote; that is why the
   dispatcher may show it on a tainted turn. A forget that deletes nothing whatever the answer (no
   text named, the store unavailable, more than 20 matches, no match) shows no card: `card` returns
   `None`, and the dispatcher then asks nothing and runs the call at once, so the model reads why
   nothing was deleted. Such a card asked the person to approve the forget of a fact they had just
   asked to keep ([readings](../readings/forget-that-deletes-nothing.md)). The tool keeps the ids it
   listed under the call's id, and `invoke` deletes exactly those, so a row written after the card
   was shown is never deleted unseen. The ids live in the brain process only between the card and
   the answer to it, the same span the dispatcher holds the call. After the delete it searches again
   and reports any row still matching, so the reply never claims a fact is gone while a row holds
   it.
   A turn whose model named it in a call is not recorded to memory, whether the call ran, was
   refused, was cut from its round or could not be read, because its query or reply may name the
   text it forgets, and recording it would store that text again. That holds for the deep phase
   of a turn the cortex handed over after naming it, which reads the cortex's runs from the
   stored reply and the mark from the handoff record. One turn is recorded all the same: every
   call it named ran and matched nothing, and its message asks to remember something, read by
   `asks_kept` (`memory_request.py`: "remember", "keep in mind", "forget" after "don't", "do
   not" or "never", or "note" before "that", "down" or the message, at a clause start, English
   only, and not "remember not to" before a keep verb and the message) and not read by
   `asks_not_kept`. The cortex calls the tool with the fact as the text on about one request to
   remember in four, and that turn has nothing to forget
   ([readings](../readings/forget-no-match-on-remember.md)). A forget request naming a value
   never stored matches nothing too, which is why the message decides. The tool sets
   `ToolResult.matched_nothing` on that run, and `TaintLedger` counts the calls named
   (`forget_calls`, an unreadable one included) and the runs that matched nothing
   (`forget_unmatched`). The handoff record keeps both counts, so a deep phase reads the cortex's
   calls the same way. So every result a call to it gets ends with
   `FORGET_NOT_KEPT_NOTE`, whether the call ran or was declined, expired or refused: nothing in
   the message is kept, the reply must not say anything in it was noted, and anything else it
   asked to be remembered must be sent again in its own message, because a model given no note
   told the person a new fact in the same message was kept. The tool is a `ResultNote`, and the
   dispatcher appends the note after it writes the audit line, which keeps the outcome alone. Its
   spec sets `private_arguments`, so the tool audit and a handoff record's loop tail keep the
   `text` argument as `<redacted>`, and a call whose arguments do not parse is logged by its tool
   name and length.
   A forget the person declined before a handoff therefore matches no call after it: the deep
   model's forget shows a card again rather than being refused for a text nobody declined.
   A turn whose message asks not to keep something, or to forget or remove it, is not recorded
   either, whether or not the model calls the tool, because the cortex answers such a request
   with no call often enough that its exchange held the value
   ([readings](../readings/forget-request-wordings.md#a-check-of-the-no-call-case-the-candidate-2026-10-30)).
   `asks_not_kept` (`memory_request.py`) reads the message: a "don't", "never" or "no need to"
   before "save", "keep", "remember" or "write it down" at a clause start, a "you don't need
   to" before one, "not for your memory", "off the record", an imperative "forget", "erase" or
   "unlearn", and a "delete" or "remove" with "from your memory". "Remember not to", "get rid
   of" and "stop remembering" (or saving, storing, keeping, noting) count only before the
   message, so "Remember not to save files to the desktop" is a rule to store, and "drop it"
   only when it ends its clause, so "drop it off at the post office" asks nothing. A file
   request in these words ("erase notes.txt", "get rid of my old files", "stop saving my drafts")
   is read too, and its turn is not recorded. A clause starts at the sentence start, after a
   comma, colon or semicolon, or after "and", "but", "so" or "please", and "also", "just" or
   "then" may come first, so "people just forget" states a habit. After any other word those
   three, or "actually", open a request only when the message follows the verb, so "use it once
   then forget it" asks. The words after a request to remember in the same sentence are what to
   keep, so "Remember: never record calls" is a rule to store, unless they name the message
   ("it", "this", "that", "my", "any" and the like). It reads English only, as `claims_kept`
   does, and never reads a "don't forget" or a statement such as "I don't remember"; a message
   it misses is recorded as before.
   A reply that says something was forgotten, or removed from memory, on a turn whose forget
   calls deleted no row ends with `UNFORGOTTEN_CLAIM_NOTE`, which the brain appends after a typed
   check of the reply (`forget_claim.py`), because the cortex answered a forget request beside
   another question with no call, and said the value was removed while its row stayed, in 8 of
   12 draws; with the note no draw misled
   ([readings](../readings/forget-request-wordings.md#a-removal-claimed-with-no-forget-call-the-candidate-2026-10-30)).
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
