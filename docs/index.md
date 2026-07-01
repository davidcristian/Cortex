# Docs index

Start here. Rules for working in this repo: [AGENTS.md](../AGENTS.md).

## Map & plan

- [ARCHITECTURE.md](ARCHITECTURE.md) covers components, boundaries, data flow, the swap rule,
  the body/brain split, ports & traits, the two portability seams.
- [ROADMAP.md](ROADMAP.md) lists ordered vertical slices; which slice proves which gate; the
  consolidated deferred-refinements backlog (every follow-up, by origin ADR); the Phase 0
  assumptions & risks list.

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
  (models in `D:\Software\AI\Models`, knowledge base in `D:\Software\AI\Database`).
- [ADR-0005: llama.cpp as the inference engine](adr/ADR-0005-llamacpp-engine.md):
  supersedes vLLM (ADR-0001 d4); one `llama-server` per model behind the
  OpenAI-compatible API; swap = process lifecycle; embeddings on the same engine.
- [ADR-0006: Gate performance](adr/ADR-0006-gate-performance.md): path-filtered CI via
  the fail-closed in-repo classifier (`scripts/ci_paths.py`), PR-only run cancellation,
  SHA-pinned actions + dependabot, parallel `just check`.
- [ADR-0007: Model Manager v1 + llama.cpp adapter](adr/ADR-0007-model-manager-inference.md):
  `ModelManager` core port; the `LlamaCppBackend` httpx adapter behind the unchanged
  `InferenceBackend`; a pure single-resident Model Manager (no swap yet); Echo stays the
  GPU-less default, llama.cpp opt-in; the `docker/docker-compose.gpu.yml` override.
- [ADR-0008: Memory v1](adr/ADR-0008-memory-v1.md): custom-and-thin over pgvector, not
  Letta (no framework that hides control flow); `Embedder` + `MemoryStore` ports and the
  `MemoryRecaller` use-case; the pgvector adapter stays 100%-covered without a DB in CI via
  the accepted MockTransport pattern (behavior proven against the fake in CI, against real
  Postgres on the host); durable data as a named volume + export to `D:\Software\AI\Database`.
- [ADR-0009: Tools via MCP](adr/ADR-0009-tools-mcp.md): `ToolRegistry` + audited
  `ToolDispatcher` in the pure core; native function-calling (evolve `InferenceBackend`,
  not prompt-and-parse); the brain as an MCP client (`mcp` SDK v1.x behind the port); tool
  servers as sidecar containers over streamable-http (filesystem read-only-mounted, patched
  for the EscapeRoute CVEs); a thin read-only IMAP server for email over ProtonMail Bridge.
- [ADR-0010: Subagents](adr/ADR-0010-subagents.md): delegation as a native `spawn_subagent`
  tool through the audited tool loop; a `CompositeToolRegistry` merging built-in + MCP tools;
  the shared infer↔tool loop extracted from `TurnEngine`; tools-enabled depth-1 subagents over a
  Redis `TaskStore`; a dedicated `SubagentScheduler` (bounded CPU concurrency, not the GPU
  `ModelManager`); subagent inference on a CPU `llama-server`.
- [ADR-0011: Body v1](adr/ADR-0011-body-v1.md): the first host-native slice with one-turn-per-
  `Converse` streaming (`TurnEvent`), the `Hotkey` OS-backend seam (first `cfg`-gated backend +
  the stub coverage escape hatch), the Tauri app outside the gated workspace, and a React+Vite
  overlay gated at 100% + browser-validated (addendum).
- [ADR-0012: Resource governance](adr/ADR-0012-resource-governance.md): GPU-first/CPU-overflow
  subagents (revising ADR-0007/0010) with the new pure `SubagentPlacer` VRAM-budget accountant
  (`VramBudgetPlacer`, `acquire` untouched), a soft two-dimensional CPU/RAM `SubagentScheduler`
  (`ResourceBudgetScheduler`), composed at `SubagentRunner`; ledgers as live-resource (not durable)
  state; `drain()`/CUDA-OOM re-place deferred to Slice 11.
- [ADR-0013: Untrusted-content boundary](adr/ADR-0013-untrusted-content.md): prompt-injection
  defense behind the tool seams (Slice 6.5) via fail-closed `Trust` on `ToolResult`, a static
  security preamble + nonce-delimited per-result wrap, a turn-local `TaintLedger` in the shared
  loop (propagating subagent → cortex), `ToolSpec.gated` + a dispatcher gate + the one new
  `Confirmer` port (inert until the first outbound tool), memory-suppress on taint; the screening
  subagent and the real overlay confirmation adapter deferred.

New non-obvious decision → add `adr/ADR-XXXX-<slug>.md`, link it here.

## Design

- [design/overlay-ux.md](design/overlay-ux.md) covers the overlay's UX & visual language (Slice 8):
  the bubbly/alive/colorful identity, design tokens, the panel anatomy, the interaction state
  machine (incl. dismiss-while-processing → corner orb → response preview), chats-as-sessions,
  keyboard shortcuts, and how it maps to the `BrainBridge` port + the store. Agents building
  overlay components follow it.

## Contracts

- [proto/body.proto](../proto/body.proto) is the body↔brain seam (single source of truth).
- [modules/](modules/) holds one short contract doc per module (purpose, public contract,
  invariants, dependencies). Every module lands with its doc:
  - [brain-core.md](modules/brain-core.md) covers `cortex_core`: pure brain logic (routing,
    conversation + memory domains, ports, the turn engine, the memory recaller, fakes).
  - [brain-session.md](modules/brain-session.md) covers `cortex_session`: Redis adapters for the
    `SessionStore` and `TaskStore` (subagent tasks, ADR-0010) hot-state ports.
  - [brain-inference.md](modules/brain-inference.md) covers `cortex_inference`: llama.cpp
    adapter for the `InferenceBackend` port (OpenAI-compatible HTTP streaming).
  - [brain-embedding.md](modules/brain-embedding.md) covers `cortex_embedding`: llama.cpp CPU
    adapter for the `Embedder` port (OpenAI `/v1/embeddings`).
  - [brain-memory.md](modules/brain-memory.md) covers `cortex_memory`: pgvector adapter for the
    `MemoryStore` port (Postgres, cosine ranking).
  - [brain-tools.md](modules/brain-tools.md) covers `cortex_tools`: MCP-client adapter for the
    `ToolRegistry` port + the logging audit sink (ADR-0009).
  - [brain-email.md](modules/brain-email.md) covers `cortex_email`: standalone read-only IMAP MCP
    server over ProtonMail Bridge (ADR-0009).
  - [brain-seam.md](modules/brain-seam.md) covers `cortex_seam`: committed wire stubs + facade.
  - [brain-orchestrator.md](modules/brain-orchestrator.md) covers `cortex_orchestrator`:
    the gRPC service hosting `BrainService`.
  - [body-core.md](modules/body-core.md) covers `body_core`: pure host types + ports
    (hotkey chord, `BrainTransport`).
  - [body-rpc.md](modules/body-rpc.md) covers `body_rpc`: tonic adapter for `BrainTransport`.
  - [body-os.md](modules/body-os.md) covers `os_windows`/`os_linux`/`os_macos`: per-platform OS
    backends (the `Hotkey` seam; real Windows, cfg-gated stubs elsewhere).
  - [body-app.md](modules/body-app.md) covers `body/app`: the React overlay (gated 100%) + its
    host-native Tauri shell (`cortex-body`).
  - [repo-gates.md](modules/repo-gates.md) covers `scripts/`: linecap + coverage gate CLIs.

## Runbooks

- [runbooks/local-dev-wsl.md](runbooks/local-dev-wsl.md) covers the daily dev loop: brain
  natively or in Compose, env vars, the live seam check, Docker Desktop notes.
- [runbooks/llamacpp-gpu.md](runbooks/llamacpp-gpu.md) covers Slice 4 host half: bring up the
  GPU compose override, run the integration test, measure VRAM, lock the final picks.
- [runbooks/memory-pgvector.md](runbooks/memory-pgvector.md) covers Slice 5 host half: bring up
  Postgres+pgvector and the CPU embedder, run the memory/embedder integration tests.
- [runbooks/tools-mcp.md](runbooks/tools-mcp.md) covers Slice 6 host half: bring up the filesystem
  MCP sidecar (streamable-http, read-only mount), run the tools integration test.
- [runbooks/email-imap.md](runbooks/email-imap.md) covers Slice 6 host half: bring up the read-only
  IMAP MCP server against a live ProtonMail Bridge, run the email integration test.
- [runbooks/subagents-cpu.md](runbooks/subagents-cpu.md) covers Slice 7 host half: bring up the CPU
  subagent `llama-server`, validate delegation (integration test + cortex-driven full stack).
- [runbooks/body-overlay.md](runbooks/body-overlay.md) covers Slice 8: run the overlay in a browser
  (fake bridge) or as the real Tauri app on Windows (hotkey → overlay → live brain).
- Expected as later slices land: `model-swap.md` (Slice 11).
