# ADR-0001: Founding architecture

**Status:** Accepted (2026-06-28; decision 4's engine replaced by ADR-0005)

## Context

Cortex is a personal, local-first assistant: inference, memory and state live on the machine, and
only tools reach external services. It is maintained long-term by agents with small context
windows. Three model tiers (a resident ~9-12B cortex, 2-4B subagents, an on-demand ~31B brain)
share one 24 GB GPU, so models are loaded and unloaded at any time. The overlay, hotkey and
OS-control features need host OS access that does not cross the WSL2 and container boundary
cleanly on Windows, while the inference and orchestration ecosystem is Python-first. Development
happens in WSL, Docker and the app run on Windows, and a later move to macOS or Linux is plausible.

## Decision

1. **External state is what makes a swap safe (the hard rule).** All conversation, task and working
   state lives in external stores, never in a model-server process or a KV cache. Every model
   instance is stateless and disposable, and a handoff is serialize, swap, rehydrate, run, persist,
   swap back. A `ModelManager` controls GPU residency and leases a model to each caller, and the
   `SessionStore` is the single source of truth for context. Every interface is designed around
   this from the start, because adding it later is a rewrite.

2. **Hexagonal (ports and adapters) on both sides of the language boundary.** A pure, I/O-free core
   holds domain types and application logic and depends only on ports (Python `Protocol`s, Rust
   traits). Adapters are thin translators and the only place external systems are touched. A port
   is defined, contract-tested and faked before any real adapter exists, and the real adapter
   passes the same checks as the fake; how those shared lists are kept is
   [ADR-0068](ADR-0068-port-contract-lists.md).

3. **A polyglot body and brain split joined by gRPC, with no FFI.** The brain (inference,
   orchestration, memory, MCP tool servers) is Python 3.12+ with `uv`, dockerized. The body and
   overlay UI are one host-native Rust (stable) and Tauri process with OS trait backends and a
   transport client, holding no business logic. The language boundary is exactly the process
   boundary and stays a network boundary: [proto/body.proto](../../proto/body.proto) is the single
   source of truth for everything on the wire, and tonic and the Python stub are both generated
   from it ([ADR-0003](ADR-0003-seam-codegen.md)). There is no PyO3 or other in-process FFI,
   because it would fuse deployment lifecycles, break the container and host split, and let types
   diverge out from under one of the two toolchains.

4. **The inference engine sits behind `InferenceBackend`.** Every engine- and hardware-specific
   setting lives in the adapter and its runbook, never in the core, so a new engine is a new
   adapter. The first engine named here was vLLM; once the model lineup was fixed to GGUF artifacts
   ([ADR-0004](ADR-0004-model-lineup.md)), [ADR-0005](ADR-0005-llamacpp-engine.md) replaced it with
   llama.cpp, which was an adapter decision, as this design intended.

5. **Stores: Redis and Postgres with pgvector.** Redis holds hot session and task state, which is
   what survives a swap; Postgres with pgvector holds durable data and vector memory. Both sit
   behind repository ports (`SessionStore`, `MemoryStore` and their siblings), and embeddings come
   from a local model behind an `Embedder` port.

6. **Toolchains and checks.** Python 3.12+ with `uv`, `ruff`, `pyright` in strict mode (chosen over
   `mypy --strict` for speed and stronger `Protocol` inference) and pytest at 100% line and branch
   coverage; Rust stable with `cargo fmt`, clippy at `-D warnings` and `cargo llvm-cov` at 100%; a
   300-line limit on every non-test `.py`, `.rs`, `.ts` and `.tsx` file; a doc-first definition of
   done; and one `just check` over both toolchains, mirrored by pre-commit and by GPU-less CI. The
   overlay's TypeScript is held to the coverage requirement and the line limit since it grew real
   logic ([ADR-0011](ADR-0011-body-v1.md) decisions 6 and 12). [AGENTS.md](../../AGENTS.md) is the
   contract and [ADR-0002](ADR-0002-toolchain-checks.md) the mechanics.

7. **Generated code is exempt from the line limit and from coverage.** Protobuf and tonic stubs
   live only in directories named `_generated`, which the line-limit scan skips and the coverage
   configuration of both toolchains excludes. Hand-written wrappers around them are normal code and
   fully checked.

8. **Orchestration stays explicit.** Routing and handoff are typed code in the core, tested with
   fakes. No framework that hides control flow is used; a helper library adopted later would sit
   behind an interface and get its own decision.

## Consequences

- Any model can be evicted mid-task and the system resumes from the store. The cost is that every
  workflow is written as explicit serialize and rehydrate steps and tested that way, including
  chaos tests that kill a model mid-task.
- The pure core makes 100% line and branch coverage achievable. GPU, OS and network specifics are
  confined to adapters, which must pass the same checks as the fakes, with an `integration`-marked
  live suite excluded from coverage and CI.
- Two toolchains cost setup effort once but keep each language where it is strongest, and the proto
  file keeps their contract from diverging.
- Portability means writing new adapters (OS crates, an inference backend), not rewrites.

## Questions the founding review left open

Each of the six is now settled where named.

1. **A memory framework or a lean layer over pgvector**: a custom layer behind `MemoryStore`
   ([ADR-0008](ADR-0008-memory-v1.md)).
2. **Body capabilities as MCP tools or as internal tools**: internal built-in tools dispatched
   through the core's tool registry over the `BodyGateway` port
   ([ADR-0023](ADR-0023-body-gateway-volume.md) decision 1).
3. **Which side opens the brain to body connection**: the brain connects to the body's
   `BodyService`, with a tunnel over a body-opened stream kept as the fallback the port leaves room
   for (ADR-0023 decision 6).
4. **Concrete models per tier**: the candidate sets and picks are
   [ADR-0004](ADR-0004-model-lineup.md), on llama.cpp (ADR-0005).
5. **The default global hotkey**: `ctrl+alt+space`, configurable through `CORTEX_HOTKEY`
   ([ADR-0011](ADR-0011-body-v1.md) decision 5).
6. **Which checks the webview frontend must pass**: first lint and format only, then 100% coverage
   and the line limit once it grew real logic (ADR-0011 decisions 6 and 12); the stylesheet and
   markup stay outside the limit.

## Alternatives rejected

- **In-process FFI (PyO3) between body and brain**, for the reasons in decision 3.
- **`mypy --strict`** in place of `pyright` strict, for speed and `Protocol` inference.
- **An agent framework that controls the flow of execution** (decision 8).

## Related

- [AGENTS.md](../../AGENTS.md), [docs/ARCHITECTURE.md](../ARCHITECTURE.md).
- [ADR-0002](ADR-0002-toolchain-checks.md), [ADR-0003](ADR-0003-seam-codegen.md),
  [ADR-0005](ADR-0005-llamacpp-engine.md), [ADR-0068](ADR-0068-port-contract-lists.md).
