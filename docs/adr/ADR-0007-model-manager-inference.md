# ADR-0007: Model Manager v1 and the llama.cpp inference adapter

- **Status:** Accepted (Slice 4 design; maintainer approved the CI-gated build, 2026-06-29)
- **Date:** 2026-06-29

## Context

Slice 4 (docs/ROADMAP.md) delivers the first real inference: a llama.cpp adapter behind
the `InferenceBackend` port and Model Manager v1 that owns the GPU. Slice 3 shipped the
port and `EchoInferenceBackend`; the composition root still wires Echo. The constraints
that shape this design: the one hard rule (no state in a model process, per AGENTS.md), gate
3 (CI is GPU-less and inference-free; real GPU/network calls live only in
`integration`-marked adapter tests), gate 2 (100% line+branch **without** a GPU), gate 1
(≤ 300 lines/file), ports-before-adapters, ADR-0005 (one `llama-server` per model,
OpenAI-compatible HTTP as the adapter surface), and ADR-0004 (logical model ids, models
bind-mounted read-only from `D:\Software\AI\Models`).

## Decisions

1. **`ModelManager` is a new core port; `InferenceBackend` is unchanged.** The
   `TurnEngine` and the whole core keep talking only to
   `InferenceBackend.stream(model, messages)`. GPU ownership sits behind a second port,
   `ModelManager`, defined in `cortex_core` because later core use-cases drive it
   directly (Slice 7 co-residency, Slice 11 handoff evict/load, per ROADMAP). In Slice 4 its
   only consumer is the llama.cpp adapter, but it is a genuine seam (real adapter + fake +
   contract test), so it is a port now.
   - `ModelManager.acquire(model) -> AbstractAsyncContextManager[ModelLease]`: entering
     queues for GPU access and yields a `ModelLease`; exiting releases it so the next
     waiter proceeds. `ModelLease.endpoint -> str` is the base URL of the `llama-server`
     serving that model. Acquiring a model that is not the resident one raises
     `ModelUnavailableError` (swap is Slice 11).

2. **The llama.cpp adapter composes the Model Manager behind `InferenceBackend`.**
   `LlamaCppBackend(model_manager, http_client)` (package `cortex_inference`): `stream`
   does `async with model_manager.acquire(model) as lease`, POSTs the OpenAI
   `/v1/chat/completions` request (`stream=true`) to `lease.endpoint`, parses the SSE
   `delta.content` deltas until `[DONE]`, and yields them. `Message` maps to OpenAI
   `{role, content}` (`USER→user`, `ASSISTANT→assistant`). Every HTTP/transport/decode
   failure crosses the port as `InferenceError` (cause chained). The core is untouched;
   the manager stays a collaborator wired at the composition root (DI at the edge).
   `cortex_inference`'s source depends only on `cortex_core` (the ports); its tests inject
   the pure `SingleResidentModelManager` from core.

3. **Model Manager v1 is a pure policy object in `cortex_core`, not a process manager.**
   "No swap yet" (ROADMAP): the single resident `llama-server` is brought up declaratively
   by `docker/docker-compose.gpu.yml`. `SingleResidentModelManager(resident_model, endpoint)` (in
   `cortex_core.model`) implements the `ModelManager` port with pure policy, namely
   single-resident enforcement (`acquire` of any other id raises `ModelUnavailableError`)
   and serialized GPU access via an `asyncio.Lock` whose waiter queue **is** the "queue
   API". It does no I/O, so it lives in the core as a reference impl (like
   `InMemorySessionStore` / `EchoInferenceBackend`) and is fully covered in CI. Process
   lifecycle (start on load, stop on unload, per ADR-0005's swap mechanism) is real I/O and
   lands in a `cortex_model_manager` adapter package in Slice 11, passing this slice's
   `ModelManager` contract unchanged; building it now would be dead code with nothing
   real to exercise it until the swap exists.

4. **Echo stays the default runtime backend; llama.cpp is opt-in by env.** `just check`
   and CI remain inference-free (gate 3) and the GPU-less dev loop keeps working.
   `wiring.run_from_env` selects `LlamaCppBackend` only when
   `CORTEX_INFERENCE_BACKEND=llamacpp` (with `CORTEX_INFERENCE_ENDPOINT` set); otherwise
   `EchoInferenceBackend`. The GPU path is exercised on the host via the gpu compose
   override and integration-marked tests.

5. **`docker/docker-compose.gpu.yml` override** adds a `llama-cortex` service (pinned llama.cpp
   CUDA server image, `--model /models/<artifact>.gguf -ngl 99 --host 0.0.0.0`, GPU
   device reservation, `D:\Software\AI\Models:/models:ro` read-only bind mount,
   loopback-only publish, per assumption 5) and sets the brain service's
   `CORTEX_INFERENCE_BACKEND`/`CORTEX_INFERENCE_ENDPOINT`. The exact image tag, flags,
   context size, and per-tier model artifacts are measured on the host and recorded in
   `docs/runbooks/llamacpp-gpu.md` and ADR-0004's final picks, the one part of this slice
   that needs the GPU and the user.

6. **Integration boundary.** Live streaming against a real `llama-server` is
   `@pytest.mark.integration` (excluded from CI + the coverage gate by the workspace
   addopts, exactly like the Redis live test). The manager's policy logic and the
   adapter's SSE parsing + error mapping are unit-tested against a fake HTTP client and a
   fake manager (100% line+branch without a GPU or network).

## Consequences

- One new workspace package is `cortex_inference` (the llama.cpp `InferenceBackend`, an
  httpx adapter), with a `docs/modules/` contract; `cortex_core` gains the
  `ModelManager` / `ModelLease` ports, the pure `SingleResidentModelManager`, and
  `ModelManagerError` / `ModelUnavailableError`. The `cortex_model_manager` package (repo
  map) is deferred to Slice 11, when process lifecycle gives it real I/O to adapt.
- The `ModelManager` seam later slices extend (co-residency, real swap) exists now with a
  contract test; Slice 11 adds process lifecycle behind the same port without touching the
  core.
- The slice splits into a **CI-gated half** (everything above, green under `just check`
  without a GPU) and a **host-only half** (VRAM measurement, final model picks, runbook
  numbers, live integration tests). The second is host-driven.
- Risks flagged for host validation: the exact `llama-server` SSE shape (assumed OpenAI
  `delta.content` / `[DONE]`), VRAM fit of the 12B cortex + KV (ROADMAP assumption 1), and
  swap latency from the Windows bind mount (assumption 2). All are measured in the host half.
- **Host-validated 2026-06-29** (ADR-0004 addendum): the live integration test streams a
  real completion through `LlamaCppBackend` against llama.cpp on the 24 GB card. The SSE
  shape assumption holds; a multimodal cortex fits at ~11 GB (16K ctx); load is
  mount-read bound. The context-size and `-ngl` (CPU/hybrid) knobs were added to
  `docker/docker-compose.gpu.yml` as a result.
