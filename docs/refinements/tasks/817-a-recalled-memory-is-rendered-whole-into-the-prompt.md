# A recalled memory is rendered whole into the prompt

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 4
**Verified:** 2026-10-07

`_render_memory_context` in `brain/packages/core/src/cortex_core/turn_context.py` writes the whole
text of every recalled memory into the system context message, and a turn recalls up to
`DEFAULT_RECALL_K` (5) of them into a cortex context of 16384 tokens (`CORTEX_CTX_SIZE`). Nothing
bounds that block.

Until 2026-10-07 the embedder's own refusal bounded it by accident: an exchange over the embedder's
2046 tokens of text failed its memory write, so no stored memory was longer than that. Since the
core embeds only the first `EMBED_INPUT_CHARS` characters and stores the whole text, an exchange of
any length is recorded ([readings](../../readings/embedding-input.md)). A pasted document of most
of the cortex's context is recorded whole, and every later turn that recalls it, in any chat under
the default global scope, can overflow the context and end with the overflow note.

The fix is a budget on what the memory block renders, per memory or for the block, with a marker
where a memory is cut. The tainted branch passes the same text to `taint.ingest_untrusted`, so the
fix must choose whether the ledger receives the cut text or the whole one. Measure first how large
the block gets over real exchanges and what the cortex's overflow point leaves for history.

## History

- 2026-10-07: filed when the core started bounding what it embeds, which made exchanges of any
  length recordable.
