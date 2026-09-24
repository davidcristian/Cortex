# ADR-0005: llama.cpp as the inference engine

**Status:** Accepted (2026-09-10); supersedes [ADR-0001](ADR-0001-architecture.md) decision 4's
choice of vLLM

## Context

[ADR-0004](ADR-0004-model-lineup.md) fixed the model candidates, all GGUF artifacts. vLLM's GGUF
support is experimental and per architecture, and the founding vLLM choice brought a class of
consumer-hardware quirks (SM120/FP8 config, FlashInfer, the CUDA-graph-capture hang on WSL2) that
needed a runbook of their own. This is a consumer program on a consumer GPU, not a throughput
serving deployment.

The brain reaches the engine over HTTP through two generation clients: the resident tier's, which
the deep tier also streams through after a handoff, and the subagent pool's. A client that waits
forever on a server that took a request and then stopped sending blocks a turn, and the model lease
under it, with nothing reported. The engine itself is pulled as a container image by a mutable tag,
so which build serves a request is decided by whoever last pulled.

This record covers the engine, how the brain talks to it, and how a reader tells which build is
running. How a generation is bounded and a cut-off reported is
[ADR-0048](ADR-0048-generation-bounds.md); the thinking switch and the trace budget are
[ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md); the live probes that measure them are
[ADR-0050](ADR-0050-live-probe-records.md).

## Decision

1. **llama.cpp is the engine behind `InferenceBackend`.** Native GGUF (the artifacts run as
   downloaded), first-class CUDA on consumer GPUs, and none of the vLLM on WSL2 quirks. The GPU
   runbook is [llamacpp-gpu](../runbooks/llamacpp-gpu.md).
2. **One `llama-server` process per loaded model**, with its OpenAI-compatible HTTP API (chat
   completions and embeddings) as the interface the adapter uses. The `InferenceBackend` adapter is
   a thin HTTP client and is faked in tests like every other adapter.
3. **The Model Manager's swap mechanism is process lifecycle.** Load starts a `llama-server` on the
   artifact; unload stops the process. This makes the hard rule literal: a swap kills the serving
   process, so anything not in the external store is gone. The lease and queue design of ADR-0001
   is unchanged; the model host that supervises the processes is
   [ADR-0030](ADR-0030-brain-handoff.md).
4. **Embeddings run on the same engine** (the nomic-embed GGUF candidates of ADR-0004): one engine
   for every tier and the embedder, and one way of accounting for VRAM, per process.
5. **GPU deployment stays dockerized** through the NVIDIA container toolkit in the
   `docker/docker-compose.gpu.yml` override, with models bind-mounted read-only from
   `CORTEX_MODELS_DIR` (ADR-0004).
6. **Portability improves.** llama.cpp runs Metal and CPU builds, so a future macOS move can likely
   reuse this adapter against a Metal build (the second portability boundary in AGENTS.md), and a
   CPU build allows GPU-less local experiments. CI stays inference-free either way.

### The generation clients

7. **The read phase of both generation clients is bounded by a per-tier stall timeout.**
   `builders.build_generation_client(stall_timeout_s)` is the one place a generation client is
   built. Connect, write and pool share `LLAMACPP_CONNECT_TIMEOUT_S` (10 s), since a dead server is
   dead at the same speed everywhere; the read phase takes the tier's own number.
   - **It detects a stall; it does not limit the generation.** httpx applies a read timeout to one
     socket read, so what it bounds is the gap between two SSE chunks: a reply that keeps arriving
     streams as long as the model wants, and one that stops arriving fails. The longest legitimate
     gap is therefore the time to first token. The credit limit on the gRPC stream
     (`CORTEX_SEAM_CONVERSE_BUFFER`) suspends the reader between reads rather than inside one, so a
     slow consumer uses none of the timeout.
   - **Two settings, because the worst legitimate silence differs by an order of magnitude.**
     `CORTEX_INFERENCE_STALL_TIMEOUT_S` (120 s) covers the resident tier and the deep tier behind
     it: about 2.6 times the worst measured time to first token once that is scaled by how much
     slower the deep pick loads than the cortex pick, a margin that covers the deep tier's own
     first token, which was never measured directly. `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` (600 s) is
     twice the slow end of a whole CPU subtask, which bounds any one call's first token there. One
     shared number would have to be the loose one, and a stuck cortex stream would then block a
     turn for the CPU tier's whole allowance. Both are positive `pydantic-settings` fields, retuned
     without a rebuild. The measurements are in [generation
     bounds](../readings/generation-bounds.md).
   - **A stall crosses the port as `InferenceError`, named apart from a dead server**
     (`_transport_failure` in `backend.py`), so an operator is not sent looking for a connection
     problem when the server took the request and then stopped sending.
   - The timeout cannot detect a model that keeps talking; that limit is ADR-0048. The run deadline
     must outlast the subagent timeout, which [ADR-0047](ADR-0047-delegated-run-bound-ordering.md)
     enforces at startup.

### Which build is running

8. **The stack names llama.cpp by mutable tags, and fixing a digest is left to the deployment.**
   The subagent, roster and memory compose files name `ghcr.io/ggml-org/llama.cpp:server`;
   `brain/Dockerfile.modelhost` builds both stages `FROM ghcr.io/ggml-org/llama.cpp:server-cuda`.
   No `@sha256` and no `pull_policy` appear, so a cached image stays until somebody pulls. Fixing a
   digest would make the tag mean one thing and turn every upstream fix into a commit here, which
   is a deployment choice rather than a design one. A reader establishes which build is behind a
   tag in three ways that agree: the image's `org.opencontainers.image.version` and `revision`
   labels (`docker image inspect`, no server needed), `build_info` at `GET /props`, and the
   `system_fingerprint` llama-server puts on every completion, both written `bNNNNN-<commit>`. A
   figure measured on the engine is dated and names the build it was taken on.
9. **A running stack records the build of every generation server it talks to, off the replies it
   already reads.** llama-server names its build on every streamed chunk as `system_fingerprint`,
   the same string as `build_info` at `/props` (read 2026-09-24 off `server` `b10680-d7bd3bfca`:
   every chunk of a stream has it). `LlamaCppBackend` reads it in `decode.py` and logs
   `model now served by engine build` with `model`, `endpoint` and `build` the first time a model's
   completion names a build and again whenever that model's build changes, so the build behind any
   logged completion is the one on the latest such line for its model. This covers the cortex in
   every `CORTEX_VISION` mode, the deep tier and both subagent placements, and costs no request. The
   build stays out of `InferenceEvent`: no core decision reads a build, and a tag moving under a
   running stack makes a build comparison the wrong test (ADR-0049). The vision probe's `vision
   probe answered` line also names `build`, the `build_info` off the `/props` body it already
   parses. The [subagent runbook](../runbooks/subagents-cpu.md) shows the first line and the vision
   runbook the second, which puts both fields under [ADR-0045](ADR-0045-documented-log-lines.md).
   A chunk whose build is absent, empty or not a string logs nothing; on the probe's line an absent
   or non-string build renders `None`.
10. **Engine flags stay adapter and runbook concerns, and a flag the build does not know fails the
    server at startup.** The core never sees a llama.cpp flag or version. A deployment that names
    no optional setting emits no flag at all rather than the engine's default written out, so an
    older build starts with the argv it always had.

## Consequences

- vLLM's continuous batching and paged attention are given up; for a single user llama.cpp's
  single-stream latency is what matters.
- Swap latency is dominated by process start and GGUF load from the model mount.
- A stack started on a machine with no cached image runs whatever the tag resolves to that day.
  Each tag resolved to a new digest at each of three registry readings over five days while the
  cached images here stayed on one build, so a reading's build stays the running one only until
  somebody pulls.
- A stall is reported as a stall. A legitimately slow first token under either timeout would be
  reported as one too, which is why both are set loose: what they remove is "forever", not "slow".
- A server records its build only once the brain streams a completion from it. The embedder records
  none: its `/v1/embeddings` reply names no build on `b10680`.

## Alternatives rejected

- **vLLM**: experimental GGUF support and a class of WSL2 quirks, for throughput a single user does
  not need.
- **One stall timeout for both clients**: it would have to be the CPU tier's number.
- **Reading the build in another probe.** The trace-setting probe's refusal body contains no
  fingerprint, so it would need a second request. The model host's readiness probe could read
  `/props` when a child first serves, but that is a second request, a wider `HealthProbe` return
  and new state in the supervisor, and it would miss the CPU subagent servers, which are compose
  services rather than model host children and run `server`, pulled apart from `server-cuda`.
- **A build field on `InferenceEvent`.** It would change the port, the fakes and every consumer of
  the stream to pass a value no core decision reads; the adapter can log it where it reads it.
- **An MLX adapter for macOS**, which ADR-0001 anticipated: a Metal build of this engine likely
  makes it unnecessary.

## Related

- [ADR-0004](ADR-0004-model-lineup.md) (lineup), [ADR-0007](ADR-0007-model-manager-inference.md)
  (the adapter), [ADR-0030](ADR-0030-brain-handoff.md) (the model host),
  [ADR-0047](ADR-0047-delegated-run-bound-ordering.md), [ADR-0048](ADR-0048-generation-bounds.md),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md),
  [ADR-0050](ADR-0050-live-probe-records.md).
- Runbooks: [llamacpp-gpu](../runbooks/llamacpp-gpu.md),
  [subagents-cpu](../runbooks/subagents-cpu.md), [vision](../runbooks/vision.md).
- Module contracts: [brain-inference](../modules/brain-inference.md),
  [brain-orchestrator](../modules/brain-orchestrator.md).
- Readings: [generation bounds](../readings/generation-bounds.md).
