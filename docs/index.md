# Docs index

Start here. Rules for working in this repo: [AGENTS.md](../AGENTS.md).

## Map & plan

- [ARCHITECTURE.md](ARCHITECTURE.md) covers components, boundaries, data flow, the swap rule,
  the body/brain split, ports & traits, the two portability seams.
- [ROADMAP.md](ROADMAP.md) lists ordered vertical slices; which slice proves which gate;
  the Phase 0 assumptions & risks list.

## Decisions (ADRs)

- [ADR-0001: Founding architecture](adr/ADR-0001-architecture.md): hexagonal on both
  sides, polyglot split with a gRPC seam (no FFI), external state as swap safety, vLLM
  behind `InferenceBackend`, Redis + Postgres/pgvector, toolchain gates; open questions.

New non-obvious decision → add `adr/ADR-XXXX-<slug>.md`, link it here.

## Contracts

- [proto/body.proto](../proto/body.proto) is the body↔brain seam (single source of truth).
- [modules/](modules/) holds one short contract doc per module (purpose, public contract,
  invariants, dependencies). Empty until Slice 1; every module lands with its doc.

## Runbooks

- [runbooks/](runbooks/) holds operational guides. Expected as slices land:
  `local-dev-wsl.md` (Slice 2), `blackwell-vllm.md` (Slice 4), `model-swap.md`
  (Slice 11).
