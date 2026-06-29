# brain/packages/embedding (`cortex_embedding`)

**Purpose.** The llama.cpp adapter for the core's `Embedder` port (ADR-0005, ADR-0008). A
thin HTTP translator: it POSTs one text to a CPU `llama-server`'s OpenAI-compatible
`/v1/embeddings` endpoint and returns the embedding vector. No orchestration, no state (the
one hard rule). The core keeps talking only to `Embedder`. Unlike the inference adapter it
is **not** routed through the `ModelManager`: embeddings run on their own CPU server
(`-ngl 0`), separate from the GPU cortex (ADR-0004 addendum says the GPU budget is the
cortex's).

**Public contract** (everything importable from `cortex_embedding`; `__all__` is the API):

- `LlamaCppEmbedder(http_client: httpx.AsyncClient, endpoint: str, *, model="embedding")` is
  an `Embedder`. `embed(text)`:
  1. POSTs `{model, input: text}` to `{endpoint}/v1/embeddings`.
  2. Returns `data[0].embedding` as a `list[float]` (integer elements are coerced to float).
  - `model` is the logical id sent in the body; `llama-server` embeds with whatever model
    it was started with and ignores the value, but the OpenAI schema requires the field.
  - The injected `http_client` owns timeouts/transport (the composition root configures a
    finite timeout, since an embedding is a quick request, unlike a streamed generation).

**Error contract.** Every failure crosses the `Embedder` port as `EmbedderError` with the
cause chained:

- any transport or non-2xx status is caught as `httpx.HTTPError` and re-raised;
- a malformed response (missing `data`/`embedding`, empty `data`, a non-numeric vector
  element, non-JSON body) is caught as `KeyError`/`IndexError`/`TypeError`/`ValueError` and
  re-raised (fail-loud, never a silent empty vector).

**Invariants.**
- Stateless per call: nothing about a request outlives `embed`; the adapter holds only its
  injected client, endpoint, and model id.
- Adapter-only: real network I/O lives here, never in the core (AGENTS.md gate 3).
- Fully typed, pyright strict clean; 100% line+branch via `httpx.MockTransport`. No model,
  no network. A live call against a real CPU `llama-server` is the `integration`-marked test
  in `tests/test_embedder_live.py` (excluded from CI + coverage; `CORTEX_EMBEDDING_ENDPOINT`
  / `CORTEX_EMBEDDING_MODEL`).

**Dependencies.** cortex-core (the `Embedder` port and `EmbedderError`), httpx. The
composition root (`cortex_orchestrator.wiring`) injects the `httpx.AsyncClient` and endpoint
when memory is wired to a durable backend (the pgvector increment).
