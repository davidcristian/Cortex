# The embedder is sent no task prefix

**Status:** done 2026-11-24
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

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
- 2026-11-24: done. The premise held. Over the 22 answerable questions of `recall_corpus.py`, both
  prefixes put 19 gold notes first against 18 with none and lose none from the top 5, but in the
  worst case of a store whose older rows have no prefix and newer rows do, 2 of 22 leave the top 5
  ([readings](../../readings/embedding-input.md#the-task-prefix)). So no prefix is sent until a
  pass embeds stored rows again, or a query prefix alone is shown to be enough:
  [task 1321](1321-the-embedder-prefixes-need-a-pass-that-embeds-stored-rows-again.md).
