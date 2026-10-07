# An exchange over the embedder's context is never recorded to memory

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-07

`record_exchange` in `brain/packages/core/src/cortex_core/turn_output.py` embeds the whole
rendered exchange, question and reply, through `MemoryRecaller.record`. The CPU embedder in
`docker/docker-compose.memory.yml` now runs with a 2048-token batch, which is the context of
`nomic-embed-text-v1.5`, and `llama-server` refuses any input longer than that with a 500. The
brain catches the `EmbedderError`, logs `memory write unavailable; this exchange was not recorded
to memory` and moves on, so every exchange longer than about 1500 words is lost to memory with
only a log line to show it. On 2026-10-07 a 2602-token input failed this way
([readings](../../readings/overlay-turn-flows.md#memory-across-chats)). The same bound applies to
a recall query, since `MemoryRecaller.recall` embeds the whole question.

The fix belongs in the core, before the `Embedder` port: bound what is embedded, either by
embedding a prefix that fits and storing the whole text, or by storing one record per piece. The
first keeps one record per exchange and its recall unchanged, and needs a token bound the core can
read without the model, such as a character budget tied to the embedder's context by
`scripts/crosscheck.py`. The second changes what a recall returns. A contract test over the fake
embedder can refuse an input over a stated size, so the bound is tested without a model.

## History

- 2026-10-07: filed when an essay exchange was not recorded on the Linux shell run; the same run
  raised the embedder's batch from the default 512 tokens to 2048.
