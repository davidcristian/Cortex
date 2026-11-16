# The embedder is sent no task prefix

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-16

The model card of `nomic-ai/nomic-embed-text-v1.5-GGUF`, read 2026-11-16, says each string given to
the model needs a task instruction prefix at its start, and shows `search_query: ` before a query.
No source file under `brain/packages` contains `search_query` or `search_document`
(`git grep -nE 'search_(document|query)' -- brain/packages`), so a stored exchange and a recall
query are both embedded with no prefix.

What would close it: the recall readings drawn with `search_document: ` on stored text and
`search_query: ` on the query, beside the form with no prefix. A prefix changes every vector, so
the draw includes rows already stored without one. Then the prefixes, or the reason written down
for sending none.

## History

- 2026-11-16: filed from the model card, read when the lineup moved to the files the mount holds.
