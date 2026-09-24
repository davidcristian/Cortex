# The embedder's engine build is recorded nowhere

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-24
**Trigger:** A reading or a report that needs the build of the embedder that wrote or queried the
memory vectors: a recall figure compared across two dates in `docs/readings/ranked-recall.md`, or
recall that changed after a pull of
`ghcr.io/ggml-org/llama.cpp:server` with the same model file and memories.

The brain logs the build of every generation server from the `system_fingerprint` on its streamed
chunks (ADR-0005 decision 9). The embedder is the one llama-server that line does not cover: a
`/v1/embeddings` reply on `b10680-d7bd3bfca` has only `data`, `model`, `object` and `usage`. Its
build is still `build_info` at `GET /props` on the embedder's endpoint and the image labels of the
memory overlay's `server` tag, and nothing in the brain reads either.

Recording it means a second request from `LlamaCppEmbedder`
([embedder.py](../../../brain/packages/embedding/src/cortex_embedding/embedder.py)), since its reply
has no field to read: one `GET /props` on the first embed, logged the way the generation line is.
No port changes. It waits because no reading so far has compared vectors across builds.

## History

- 2026-09-24: Opened by the close of
  [R-622](622-only-one-endpoint-in-one-mode-records-its-engine-build.md), which records every
  generation server's build and found the embeddings reply names none.
