# ADR-0007: Model Manager v1 and the llama.cpp inference adapter

**Status:** Accepted (2026-06-29)

## Context

This slice delivers the first real inference: a llama.cpp adapter behind the `InferenceBackend`
port, and Model Manager v1, which controls the GPU. The previous slice added the port and
`EchoInferenceBackend`; the composition root still wires Echo. The constraints that shape this
design are the one hard rule (no state in a model process, per AGENTS.md), CI being GPU-less and
inference-free with real GPU and network calls only in `integration`-marked adapter tests, 100%
line and branch coverage **without** a GPU, the 300-line limit per file, ports before adapters,
ADR-0005 (one `llama-server` per model, OpenAI-compatible HTTP as the adapter's interface) and
ADR-0004 (logical model ids, models bind-mounted read-only from `D:\Software\AI\Models`).

## Decisions

1. **`ModelManager` is a new core port; `InferenceBackend` is unchanged.** The `TurnEngine` and the
   whole core keep talking only to `InferenceBackend.stream(model, messages)`. GPU ownership sits
   behind a second port, `ModelManager`, defined in `cortex_core` because later core use-cases
   drive it directly (co-residency, and evict and load during a handoff). For now its only consumer
   is the llama.cpp adapter, but it is a real port (real adapter, fake and contract test), so it is
   defined as one now.
   - `ModelManager.acquire(model) -> AbstractAsyncContextManager[ModelLease]`: entering the context
     manager queues for GPU access and yields a `ModelLease`; exiting releases it so the next
     waiter proceeds. `ModelLease.endpoint -> str` is the base URL of the `llama-server` serving
     that model. Acquiring a model that is not the resident one raises `ModelUnavailableError`,
     since swapping comes later.

2. **The llama.cpp adapter composes the Model Manager behind `InferenceBackend`.**
   `LlamaCppBackend(model_manager, http_client)` (package `cortex_inference`): `stream` does
   `async with model_manager.acquire(model) as lease`, POSTs the OpenAI `/v1/chat/completions`
   request (`stream=true`) to `lease.endpoint`, parses the SSE `delta.content` deltas until
   `[DONE]`, and yields them. `Message` maps to OpenAI `{role, content}` (`USER→user`,
   `ASSISTANT→assistant`). Every HTTP, transport and decode failure crosses the port as
   `InferenceError` with its cause chained. The core is untouched; the manager stays a collaborator
   wired at the composition root. `cortex_inference`'s source depends only on `cortex_core` (the
   ports); its tests inject the pure `SingleResidentModelManager` from core.

3. **Model Manager v1 is a pure policy object in `cortex_core`, not a process manager.** There is
   no swap yet: the single resident `llama-server` is started declaratively by
   `docker/docker-compose.gpu.yml`. `SingleResidentModelManager(resident_model, endpoint)` (in
   `cortex_core.model`) implements the `ModelManager` port with pure policy: single-resident
   enforcement (`acquire` of any other id raises `ModelUnavailableError`) and serialized GPU access
   through an `asyncio.Lock` whose waiter queue **is** the queue API. It does no I/O, so it lives
   in the core as a reference implementation (like `InMemorySessionStore` and
   `EchoInferenceBackend`) and is fully covered in CI. Process lifecycle (start on load, stop on
   unload, per ADR-0005's swap mechanism) is real I/O and goes into a `cortex_model_manager`
   adapter package with the swap, passing this slice's `ModelManager` contract unchanged; building
   it now would be dead code with nothing real to exercise it.

4. **Echo stays the default runtime backend; llama.cpp is opt-in through the environment.** `just
   check` and CI stay inference-free and the GPU-less dev loop keeps working. `wiring.run_from_env`
   selects `LlamaCppBackend` only when `CORTEX_INFERENCE_BACKEND=llamacpp` (with
   `CORTEX_INFERENCE_ENDPOINT` set); otherwise `EchoInferenceBackend`. The GPU path is exercised on
   the host through the gpu compose override and integration-marked tests.

5. **`docker/docker-compose.gpu.yml` override** adds a `llama-cortex` service (a llama.cpp CUDA
   server image named by a fixed tag, `--model /models/<artifact>.gguf -ngl 99 --host 0.0.0.0`, a
   GPU device reservation, the `D:\Software\AI\Models:/models:ro` read-only bind mount and a
   loopback-only publish) and sets the brain service's `CORTEX_INFERENCE_BACKEND` and
   `CORTEX_INFERENCE_ENDPOINT`. The exact image tag, flags, context size and per-tier model
   artifacts are measured on the host and recorded in `docs/runbooks/llamacpp-gpu.md` and
   ADR-0004's final picks, the one part of this slice that needs the GPU and the maintainer.

6. **Where the boundary with live systems is.** Live streaming against a real `llama-server` is
   `@pytest.mark.integration` (excluded from CI and from the coverage requirement by the workspace
   addopts, exactly like the Redis live test). The manager's policy logic and the adapter's SSE
   parsing and error mapping are unit-tested against a fake HTTP client and a fake manager, at 100%
   line and branch coverage without a GPU or network.

## Consequences

- One new workspace package, `cortex_inference` (the llama.cpp `InferenceBackend`, an httpx
  adapter), with a contract doc in `docs/modules/`; `cortex_core` gains the `ModelManager` and
  `ModelLease` ports, the pure `SingleResidentModelManager`, and `ModelManagerError` and
  `ModelUnavailableError`. The `cortex_model_manager` package in the repo map waits for the swap,
  when process lifecycle gives it real I/O to adapt.
- The `ModelManager` port that later slices extend (co-residency, real swap) exists now with a
  contract test; the swap adds process lifecycle behind the same port without touching the core.
- The slice splits in two: everything above, green under `just check` without a GPU, and a
  host-only half (VRAM measurement, final model picks, runbook numbers, live integration tests).
- Risks flagged for host validation: the exact `llama-server` SSE shape (assumed OpenAI
  `delta.content` and `[DONE]`), VRAM fit of the 12B cortex plus KV cache, and swap latency from
  the Windows bind mount. All are measured in the host half.
- **Host-validated 2026-06-29** ([model lineup readings](../readings/model-lineup.md#cortex)): the
  live integration test streams a real completion through `LlamaCppBackend` against llama.cpp on
  the 24 GB card. The SSE shape assumption holds; a multimodal cortex fits at about 11 GB (16K
  ctx); load is bound by the mount's read rate. The context-size and `-ngl` (CPU and hybrid)
  settings were added to `docker/docker-compose.gpu.yml` as a result.
