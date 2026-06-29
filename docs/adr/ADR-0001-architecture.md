# ADR-0001: Founding architecture

- **Status:** Proposed in Phase 0 (awaiting maintainer review)
- **Date:** 2026-06-28

## Context

Cortex is a personal, mostly-local assistant maintained long-term by agents with small
context windows. Three model tiers (resident ~9-12B cortex, 2-4B subagents, on-demand
~31B brain) share a single 24 GB GPU, so models are loaded and unloaded at any time. The
overlay/hotkey/OS-control surface needs host OS access that does not cross the
WSL2/container boundary cleanly on Windows, while the inference/orchestration ecosystem
(vLLM) is Python-first. Development happens in WSL; Docker and the app run on Windows; a
later move to macOS or Linux is plausible.

## Decision

1. **External state as the swap-safety mechanism (the hard rule).** All conversation,
   task, and working state lives in external stores and never in a model-server process or
   KV cache. Every model instance is stateless and disposable; a handoff is
   serialize → swap → rehydrate → run → persist → swap back. All first interfaces are
   designed around this; a `ModelManager` service owns the GPU and exposes a queue, and
   the `SessionStore` is the single source of truth for context.
2. **Hexagonal (ports & adapters) on both sides of the language boundary.** A pure,
   I/O-free core holds domain types and application logic and depends only on ports
   (Python `Protocol`s) / traits (Rust). Adapters are thin translators and the only place
   external systems are touched. Ports are defined, contract-tested, and faked before any
   real adapter exists.
3. **Polyglot body/brain split with a gRPC seam; explicitly no FFI.** The brain
   (inference, orchestration, memory, MCP tool servers) is Python 3.12+/`uv`,
   dockerized. The body + overlay UI is one host-native Rust (stable)/Tauri process with OS
   trait backends plus a transport client, no business logic. The language boundary is
   exactly the process boundary and stays a **network boundary**: a shared
   [proto/body.proto](../../proto/body.proto) (tonic ⇄ generated Python stub) is the
   single source of truth for everything on the wire. **No PyO3 / in-process FFI**, because
   it would fuse deployment lifecycles, break the container/host split, and let types
   drift out from under one of the two toolchains.
4. **vLLM behind `InferenceBackend`.** All Blackwell/WSL2-specific configuration
   (SM120/FP8, FlashInfer, `--enforce-eager` workarounds) lives in the vLLM adapter and
   its runbook, never in the core. A future MLX/llama.cpp backend is a new adapter.
5. **Stores: Redis + Postgres/pgvector.** Redis for hot session/task state and the event
   bus (what survives swaps); Postgres + pgvector for durable data and vector memory, with
   both behind `SessionStore`/`MemoryStore` repository ports. Embeddings come from a
   local model behind an `Embedder` port.
6. **Toolchains and gates.** Python 3.12+/`uv` (ruff, `pyright` strict, which was chosen over
   `mypy --strict` for speed and stronger `Protocol` inference, pytest at 100%
   line+branch) and Rust stable/Cargo (fmt, clippy `-D warnings`, cargo-llvm-cov at
   100%), a 300-line cap on all non-test `.py`/`.rs` files, doc-first DoD, and a single
   dual-toolchain `just check` mirrored by pre-commit and GPU-less CI
   (see [AGENTS.md](../../AGENTS.md)).
7. **Generated code is exempt from the line cap and coverage.** Protobuf/tonic stubs
   live in clearly marked generated-only directories, excluded by the line-cap scan and
   coverage config. Hand-written wrappers around them are normal code and fully gated.
8. **Orchestration stays explicit.** Routing/handoff is typed code in the core, tested
   with fakes. No framework that hides control flow; if a helper library (Pydantic AI /
   LangGraph) is ever adopted it sits behind an interface. It gets its own ADR.

## Consequences

- Any model can be evicted mid-task and the system resumes from the store; the cost is
  that every workflow must be expressed as explicit serialize/rehydrate steps and tested
  that way (chaos tests kill models mid-task).
- The pure core makes 100% line+branch coverage achievable; GPU/OS/network specifics are
  quarantined in adapters with contract tests against fakes plus an `integration`-marked
  live suite excluded from coverage and CI.
- Two toolchains cost setup effort once (Slice 1) but keep each language where it is
  strongest; the proto file prevents contract drift between them.
- Portability later = writing new adapters (OS crates, inference backend), not rewrites.

## Open questions (deferred, each will get its own ADR when resolved)

1. **Letta vs. a lean custom memory layer over pgvector** gets decided when the memory
   slice lands; hidden behind `MemoryStore` either way.
2. **Whether body capabilities (volume/screen/input) also surface as MCP tools to the
   models**, or remain internal tools dispatched via the core's `ToolRegistry` over the
   `BodyGateway`. Initial working assumption: internal tools only, revisit with real use.
3. **Brain→body connectivity direction**: default assumption is the brain dials the
   body's gRPC server via `host.docker.internal`; fallback if Windows
   firewall/portability makes that brittle is tunneling body-directed calls over a
   body-initiated bidirectional stream.
4. **Concrete model choices** (cortex, subagent, brain, embedder) and their VRAM fit have
   candidate sets locked in [ADR-0004](ADR-0004-model-lineup.md) (all GGUF, which also
   opens a vLLM-vs-llama.cpp engine question); final picks + engine decided in the
   real-inference slice with measurements.
5. **Default global hotkey** (`Win+Space` is taken on Windows) is configurable from day
   one; `Ctrl+Alt+Space` proposed in the roadmap's assumptions list, confirmed at the
   first body slice.
6. **Webview frontend gating** means the overlay's TS/HTML is kept minimal; lint/format
   gated, but the 100%-coverage and 300-line gates initially apply only to `.py`/`.rs`.
   Revisit if the frontend grows real logic.
