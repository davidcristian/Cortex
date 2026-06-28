# Roadmap of vertical slices

Each slice is a thin end-to-end path: small, green under `just check`, documented before
it is done. **Gate proven** marks the first slice that exercises each hard gate for real.
The order follows the founding spec's arc (chat → memory → tools → subagents → body →
handoff last); the two insertions are the seam skeleton at Slice 2 (pulled early because
every later slice talks over `Converse` and the seam gate should be proven before code
piles up on both sides) and real inference at Slice 4, so memory/tools/subagents build
against a real model while CI keeps using fakes.

## Slice 0 (Governance, this phase)

AGENTS.md, CLAUDE.md, docs skeleton, ADR-0001, port/trait list, proto sketch, this plan,
and the assumptions & risks list at the bottom of this file. No feature code.
**Stops for maintainer review.**

## Slice 1 (Walking skeleton): both toolchains, all gates

One trivial pure module per side (e.g. a typed routing decision in `brain/packages/core`,
a hotkey-config type in `body/crates/core`), plus: `uv` workspace, Cargo workspace,
justfile (`just check` spanning both), the line-cap script, pre-commit, and GPU-less CI
building and gating both trees.
**Gates proven:** Python 100% line+branch · Rust 100% via cargo-llvm-cov · 300-line scan
· dual-toolchain `just check` · GPU-less CI.

## Slice 2 (The seam): proto compiled on both sides

`proto/body.proto` v0 (`BrainService.Health` + `Converse` shape), tonic build in
`body/crates/rpc`, generated Python stubs in `brain/packages/seam`. That is the shared wire
code; the typed `BodyService` client wrapper (`body_client`) arrives with Slice 9. A
body-side dev command calls brain `Health` end-to-end (brain in Compose, caller on
host). Contract tests with fakes on both sides; generated-code exemption wired into the
scan/coverage config. Runbook: `docs/runbooks/local-dev-wsl.md` (brain in Compose +
host-side dev loop from WSL).
**Gate proven:** gRPC seam as single source of truth (codegen in both builds).

## Slice 3 (Cortex-only chat with fake inference)

`SessionStore` port (in-memory fake + Redis adapter behind the same contract test),
`InferenceBackend` port + scripted fake, orchestrator use-case "handle a user turn" in
the pure core; a turn arrives over `Converse`, is answered by the fake, and the session
state survives an orchestrator process restart (proving state is external).
**Gate proven:** ports-before-adapters with contract tests; repository pattern.

## Slice 4 (Real inference): vLLM adapter + Model Manager v1

vLLM adapter for `InferenceBackend` (all Blackwell/WSL2 quirks inside + runbook
`docs/runbooks/blackwell-vllm.md`); Model Manager v1: owns the GPU, single resident
model, `acquire()` lease + queue API (no swap yet); `docker-compose.gpu.yml` override.
Concrete cortex/embedder model choices recorded (ADR + runbook). Live tests are
`integration`-marked, run manually on the host.
**Gate proven:** integration suite excluded from coverage/CI; adapter as blast radius.

## Slice 5 (Memory v1): retrieval that grows

`MemoryStore` + `Embedder` ports; pgvector adapter + local embedding model (fake in CI);
memory writes at turn end, top-k retrieval into cortex context. ADR resolving
Letta vs. custom decides the implementation behind the unchanged port.

## Slice 6 (Tools via MCP): files, then email

`ToolRegistry` port + tool dispatch in the pure core (command pattern), every invocation
audit-logged; MCP filesystem server, then IMAP email server (read-only first). All later
tools (including body-backed OS actions) go through this port.

## Slice 7 (Subagents)

Delegate a narrow task to a 2-4B co-resident model: task record in the store, subagent
runs as a stateless function over it, result persisted, cortex consumes it. Exercises
`ModelManager` co-residency within the 12 GB envelope.

## Slice 8 (Body v1): hotkey → overlay → chat

Tauri app skeleton: tray + hidden window, `Hotkey` trait with Windows backend
(macOS/Linux stubs, coverage-off with reasons), overlay shows on hotkey, prompt goes
over `Converse`, streamed reply renders. Configurable hotkey.
**Gate proven:** cfg-gated OS backends; stub coverage escape hatch policy.

## Slice 9 (One OS action end-to-end, volume)

`AudioControl` Windows backend (Core Audio); `BodyService.SetVolume/GetVolume` served by
the body; brain-side `BodyGateway` port + gRPC adapter; the volume tool registers in the
Slice 6 `ToolRegistry` and dispatches through the existing audited path. "Set volume to
30%" spoken to the overlay changes host volume.
**Gate proven:** bidirectional seam (brain calls body).

## Slice 10 (Vision): "see my screen"

`ScreenCapture` Windows backend; capture flows brain-ward over the seam into the
multimodal cortex; "what's on my screen?" answered in the overlay.

## Slice 11 (Brain handoff): the swap rule, for real (capstone)

Full handoff: cortex escalates → context serialized → `ModelManager` evicts
cortex/subagents and loads the brain (vLLM sleep/offload + load) → brain rehydrates from
the store, works, persists → swap back → cortex resumes from the store. Includes a chaos
test (kill a model mid-handoff; system resumes from the store) and runbook
`docs/runbooks/model-swap.md`.
**Gate proven:** THE hard rule, end to end.

## Later (unordered)

Pointer-input injection (extend the proto first), richer memory policies, email
write-actions behind explicit confirmation, macOS/Linux backends, more subagent roles.

## Assumptions & risks to confirm (Phase 0)

Deferred *decisions* live in ADR-0001's open questions; these are the *assumptions* the
plan bets on, with what would invalidate each:

1. **VRAM fit.** A quantized ~9-12B multimodal cortex + embedder + one 2-4B subagent fit
   in 12 GB with usable KV headroom. Invalidated if the vision tower + KV blow the
   budget → smaller cortex or tighter quantization (checked in Slices 4/7).
2. **Swap latency/stability.** vLLM sleep/offload + load on Blackwell/WSL2 completes a
   cortex↔brain swap in seconds and is reliable. Slow is tolerable (the `Converse`
   stream reports swap status to the overlay); *unstable* would force full process
   restarts per swap (survivable only because of the external-state rule).
3. **Brain→body connectivity.** The dockerized brain can dial the host body's gRPC
   server via `host.docker.internal` through the Windows firewall. Fallback: tunnel
   body-directed calls over a body-initiated stream (ADR-0001 Q3).
4. **Coverage on Tauri glue.** 100% line+branch on the body holds because app wiring
   stays thin and logic lives in `body/crates/core`. If Tauri macro-generated glue
   resists instrumentation, that glue gets an ADR'd, narrowly-scoped exclusion.
5. **Security model.** Single-user machine: loopback-only listeners, shared-secret token
   on the seam via env, no mTLS. Revisit only if anything ever listens beyond loopback.
6. **Email safety.** IMAP read-only first; any send/write action lands later, behind
   explicit per-action confirmation in the overlay.
7. **Default hotkey.** `Ctrl+Alt+Space`, configurable from day one (`Win+Space` is
   taken by Windows).
