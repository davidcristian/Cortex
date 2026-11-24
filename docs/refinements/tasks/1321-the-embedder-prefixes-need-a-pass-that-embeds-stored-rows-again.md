# The embedder prefixes need a pass that embeds stored rows again

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-24

The card of `nomic-embed-text-v1.5` asks for `search_document: ` before a stored text and
`search_query: ` before a query, and the brain sends neither. Over the recall corpus, both
prefixes put one more gold note first (19 of 22 against 18), and a query prefix alone does the
same, with every other count equal
([readings](../../readings/embedding-input.md#the-task-prefix)). A row with the document prefix
scores higher against a prefixed query than the same row without it, so a store holding rows of
both forms ranks old rows low: with the gold row old and every other row new, 2 of 22 leave the
top 5. The store keeps no record of the form a row was embedded in.

## What to do

1. Write the rule before the draw: build a corpus of at least 40 answerable question and note
   pairs with near-miss notes, in a file of its own so the published numbers of
   `recall_corpus.py` stay, and draw it in the four forms of the readings. A query prefix alone
   ships, with no pass, when its count first and its count in the top 5 are each at least those
   of both prefixes and of no prefix. Both prefixes ship with the pass when either of their counts
   is above the query prefix's and none is below no prefix's. Otherwise no prefix is sent, and
   that count is the reason.
2. Give the `Embedder` port the role of a text (a stored text or a query), and let the adapter map
   each role to its prefix from a setting whose default is the card's, since
   `CORTEX_MODEL_FILE_EMBED` can name another model. Count the prefix's tokens through
   `/tokenize` against the 246 spare under the 1800 character cut.
3. If both prefixes ship: record each row's form in the `memories` table, and add a step that
   embeds every row of the old form again before the first recall, behind a `MemoryStore` method
   the fake and the pgvector store both pass a contract test on.

## History

- 2026-11-24: filed while closing
  [task 1241](1241-the-embedder-is-sent-no-task-prefix.md).
