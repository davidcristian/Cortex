# Docs index

Start here. Rules for working in this repo: [AGENTS.md](../AGENTS.md).

## Map & plan

- [ARCHITECTURE.md](ARCHITECTURE.md) covers components, boundaries, data flow, the swap rule,
  the body/brain split, ports & traits, the two portability seams.
- [ROADMAP.md](ROADMAP.md) lists ordered vertical slices; which slice proves which gate;
  the Phase 0 assumptions & risks list.

## Decisions (ADRs)

- [ADR-0001: Founding architecture](adr/ADR-0001-architecture.md): hexagonal on both
  sides, polyglot split with a gRPC seam (no FFI), external state as swap safety, the
  engine behind `InferenceBackend` (originally vLLM, now superseded by ADR-0005),
  Redis + Postgres/pgvector, toolchain gates; open questions.
- [ADR-0002: Toolchain and gate mechanics](adr/ADR-0002-toolchain-gates.md): nightly
  for Rust branch coverage, the JSON branch gate, `scripts/` as a standalone project,
  the `_generated` marker, tests-outside-source, ruff ALL, pre-commit = `just check`.
- [ADR-0003: Seam codegen and packaging](adr/ADR-0003-seam-codegen.md): committed
  stubs in `_generated` dirs (hermetic builds, `just proto` to regen), tonic + grpcio,
  `#[ignore]` tests as the Rust integration suite, stubs shared via `cortex_seam`,
  the CORTEX_SEAM_* env contract.
- [ADR-0004: Model lineup](adr/ADR-0004-model-lineup.md): locked candidate sets per
  tier + embedder (all GGUF via LM Studio), logical model ids, local data locations
  (models in `D:\Software\AI Models`, knowledge base in `D:\Software\AI Database`).
- [ADR-0005: llama.cpp as the inference engine](adr/ADR-0005-llamacpp-engine.md):
  supersedes vLLM (ADR-0001 d4); one `llama-server` per model behind the
  OpenAI-compatible API; swap = process lifecycle; embeddings on the same engine.

New non-obvious decision → add `adr/ADR-XXXX-<slug>.md`, link it here.

## Contracts

- [proto/body.proto](../proto/body.proto) is the body↔brain seam (single source of truth).
- [modules/](modules/) holds one short contract doc per module (purpose, public contract,
  invariants, dependencies). Every module lands with its doc:
  - [brain-core.md](modules/brain-core.md) covers `cortex_core`: pure brain logic (routing,
    conversation domain, ports, the turn engine, reference fakes).
  - [brain-session.md](modules/brain-session.md) covers `cortex_session`: Redis adapter for
    the `SessionStore` port.
  - [brain-seam.md](modules/brain-seam.md) covers `cortex_seam`: committed wire stubs + facade.
  - [brain-orchestrator.md](modules/brain-orchestrator.md) covers `cortex_orchestrator`:
    the gRPC service hosting `BrainService`.
  - [body-core.md](modules/body-core.md) covers `body_core`: pure host types + ports
    (hotkey chord, `BrainTransport`).
  - [body-rpc.md](modules/body-rpc.md) covers `body_rpc`: tonic adapter for `BrainTransport`.
  - [repo-gates.md](modules/repo-gates.md) covers `scripts/`: linecap + coverage gate CLIs.

## Runbooks

- [runbooks/local-dev-wsl.md](runbooks/local-dev-wsl.md) covers the daily dev loop: brain
  natively or in Compose, env vars, the live seam check, Docker Desktop notes.
- Expected as later slices land: `llamacpp-gpu.md` (Slice 4), `model-swap.md`
  (Slice 11).
