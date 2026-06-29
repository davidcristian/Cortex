# Roadmap of vertical slices

Each slice is a thin end-to-end path: small, green under `just check`, documented before
it is done. **Gate proven** marks the first slice that exercises each hard gate for real.
The order follows the founding spec's arc (chat → memory → tools → subagents → body →
handoff last); the two insertions are the seam skeleton at Slice 2 (pulled early because
every later slice talks over `Converse` and the seam gate should be proven before code
piles up on both sides) and real inference at Slice 4, so memory/tools/subagents build
against a real model while CI keeps using fakes.

Each slice carries a **Status** marker (*done* or *in progress*); slices without one are
planned and not yet started.

## Slice 0 (Governance, this phase)

**Status:** done.

AGENTS.md, CLAUDE.md, docs skeleton, ADR-0001, port/trait list, proto sketch, this plan,
and the assumptions & risks list at the bottom of this file. No feature code.
**Stops for maintainer review.**

## Slice 1 (Walking skeleton): both toolchains, all gates

**Status:** done.

One trivial pure module per side (e.g. a typed routing decision in `brain/packages/core`,
a hotkey-config type in `body/crates/core`), plus: `uv` workspace, Cargo workspace,
justfile (`just check` spanning both), the line-cap script, pre-commit, and GPU-less CI
building and gating both trees.
**Gates proven:** Python 100% line+branch · Rust 100% via cargo-llvm-cov · 300-line scan
· dual-toolchain `just check` · GPU-less CI.

## Slice 2 (The seam): proto compiled on both sides

**Status:** done.

`proto/body.proto` v0 (`BrainService.Health` + `Converse` shape), tonic build in
`body/crates/rpc`, generated Python stubs in `brain/packages/seam`. That is the shared wire
code; the typed `BodyService` client wrapper (`body_client`) arrives with Slice 9. A
body-side dev command calls brain `Health` end-to-end (brain in Compose, caller on
host). Contract tests with fakes on both sides; generated-code exemption wired into the
scan/coverage config. Runbook: `docs/runbooks/local-dev-wsl.md` (brain in Compose +
host-side dev loop from WSL).
**Gate proven:** gRPC seam as single source of truth (codegen in both builds).

## Slice 3 (Cortex-only chat with fake inference)

**Status:** done.

`SessionStore` port (in-memory fake + Redis adapter behind the same contract test),
`InferenceBackend` port + scripted fake, orchestrator use-case "handle a user turn" in
the pure core; a turn arrives over `Converse`, is answered by the fake, and the session
state survives an orchestrator process restart (proving state is external).
**Gate proven:** ports-before-adapters with contract tests; repository pattern.

## Slice 4 (Real inference): llama.cpp adapter + Model Manager v1

**Status:** done.

llama.cpp adapter for `InferenceBackend` (ADR-0005: one `llama-server` process per
model, OpenAI-compatible HTTP as the adapter surface; engine flags/quirks inside the
adapter + runbook `docs/runbooks/llamacpp-gpu.md`); Model Manager v1: owns the GPU,
single resident model, `acquire()` lease + queue API (no swap yet);
`docker-compose.gpu.yml` override with the read-only model-dir bind mount
(`D:\Software\AI\Models`, ADR-0004). Final per-tier model picks recorded against
measured VRAM (ADR-0004). Live tests are `integration`-marked, run manually on the
host.
**Gate proven:** integration suite excluded from coverage/CI; adapter as blast radius.

**Delivered (2026-06-29):** CI-gated half ([ADR-0007](adr/ADR-0007-model-manager-inference.md)):
the `cortex_inference` llama.cpp adapter behind the unchanged `InferenceBackend`, the
`ModelManager` port + pure `SingleResidentModelManager`, config-driven backend selection
(Echo default, llama.cpp opt-in), and `docker-compose.gpu.yml`. All are green under
`just check` without a GPU. Host half done too: GPU compose up, live integration tests run,
VRAM measured, and the cortex pick locked to gemma-4-12B. See
[docs/runbooks/llamacpp-gpu.md](runbooks/llamacpp-gpu.md) and the
[ADR-0004 addendum](adr/ADR-0004-model-lineup.md). The Model Manager v1 is pure
and lives in `cortex_core`; the `cortex_model_manager` package (process lifecycle) is
deferred to Slice 11, when swap gives it real I/O.

## Slice 5 (Memory v1): retrieval that grows

**Status:** done.

`MemoryStore` + `Embedder` ports; pgvector adapter + local embedding model (fake in CI;
the nomic candidates in ADR-0004 run on llama.cpp per ADR-0005); memory writes at turn
end, top-k retrieval into cortex context. ADR resolving Letta vs. custom decides the
implementation behind the unchanged port. The knowledge base's durable data lives under
`D:\Software\AI\Database` (plug-and-play requirement, ADR-0004 addendum). Validate the
Postgres-over-Windows-bind-mount caveat here; fallback (now the default, ADR-0008) is a
named volume + automated sync into that directory.

**Progress (2026-06-29):** design + first three increments landed
([ADR-0008](adr/ADR-0008-memory-v1.md)), all 100% under `just check`, no DB.
(1) The `Embedder` + `MemoryStore` core ports, the `MemoryRecord`/`ScoredMemory` values,
the `MemoryRecaller` remember/recall use-case, and the in-memory fakes
(`InMemoryMemoryStore` cosine twin of pgvector, deterministic `HashEmbedder`).
(2) Memory wired into the turn: `TurnEngine` takes an optional `MemoryRecaller`; when
present it recalls top-k into an ephemeral `Role.SYSTEM` context message (never persisted)
and records the exchange at turn end. `memory=None` keeps the old behavior, so the GPU-less
default path is unchanged.
(3) The CPU embedder adapter (`cortex_embedding`): `LlamaCppEmbedder` over a llama-server
OpenAI `/v1/embeddings` endpoint behind the `Embedder` port, 100%-covered via
`httpx.MockTransport` with an `integration`-marked live test.
(4) The pgvector adapter (`cortex_memory`): `PgVectorMemoryStore` behind the `MemoryStore`
port, 100%-covered without a DB via a canned-row fake `Database` (the asyncpg analog of
`MockTransport`); wired into `run_from_env` **opt-in** (`CORTEX_MEMORY_BACKEND`, default
`none`) alongside the embedder; `docker-compose.memory.yml` adds Postgres+pgvector + a CPU
embedder. Host half validated (2026-06-29): the memory contract passed against real
Postgres+pgvector 0.8.4 and the embedder against a live CPU `llama-server`. The nomic pick
is **nomic-embed-text-v1.5 Q8_0** (768-dim), recorded in the
[ADR-0004 addendum](adr/ADR-0004-model-lineup.md), per
[docs/runbooks/memory-pgvector.md](runbooks/memory-pgvector.md).

## Slice 6 (Tools via MCP): files, then email

**Status:** done.

`ToolRegistry` port + tool dispatch in the pure core (command pattern), every invocation
audit-logged; MCP filesystem server, then IMAP email server (read-only first). All later
tools (including body-backed OS actions) go through this port.

**Progress (2026-06-29):** design + increments 1-2 landed
([ADR-0009](adr/ADR-0009-tools-mcp.md)), 100% under `just check`, no MCP. (1) The pure
tool-dispatch core: the `ToolRegistry` + `ToolAuditSink` ports, the
`ToolSpec`/`ToolCall`/`ToolResult`/`ToolInvocation` values, the typed
`ToolError`/`ToolNotFoundError`, the `InMemoryToolRegistry` + `RecordingAuditSink` fakes, and
the stateless `ToolDispatcher` use-case. It runs a call through the registry and writes
exactly one audit record per dispatch (a registry failure becomes an `is_error` result the
model can recover from). (2) **Native function-calling in the turn:** `InferenceBackend`
now yields `InferenceEvent` (`TextChunk | ToolCall`) and takes `tools`; `Message` gained the
`tool_calls`/`tool_call_id` structure and `Role.TOOL`; `TurnEngine` runs the bounded
(`MAX_TOOL_STEPS`) inference↔tool loop behind an optional `TurnCapabilities` bundle
(dispatch is audited, results fed back, tool context in-turn only in v1); and `LlamaCppBackend`
sends the OpenAI `tools` payload and reassembles streamed `tool_calls` (needs `--jinja`). The
three forks are resolved in ADR-0009: **native function-calling**, **sidecar-over-http** tool
servers, and a **thin read-only IMAP** email server for ProtonMail Bridge. (3) **The MCP
filesystem tool** (CI half): the `cortex_tools` package with `McpToolRegistry` over the official
`mcp` SDK (pinned `>=1.23,<2`) behind an injected `McpSession` port + fake (100% without a
server), plus the `LoggingAuditSink`; wired into `run_from_env` **opt-in**
(`CORTEX_TOOLS_BACKEND`, default `none`); `docker-compose.tools.yml` adds the filesystem
server as a read-only-mounted sidecar over streamable-http. Host-validated (2026-06-29):
the live sidecar (supergateway-bridged filesystem server) passed the integration test, and
the read-only mount blocked a write (`EROFS`), with the containment boundary proven end to end
([ADR-0009 addendum](adr/ADR-0009-tools-mcp.md)). (4) **The read-only IMAP email tool** (CI
half): the standalone `cortex_email` package, which is a FastMCP server exposing read-only
list/search/read tools over **imap-tools** (STARTTLS, chosen over aioimaplib which lacks it;
the server is a sidecar, so async-nativeness doesn't apply), 100%-covered without a server;
read-only enforced three ways (only read tools register, EXAMINE, `mark_seen=False`);
`docker-compose.email.yml` runs it as a sidecar reaching the host ProtonMail Bridge.
Host-validated (2026-06-29): the sidecar reached the user's live Bridge (STARTTLS via
host.docker.internal), and dogfooding `McpToolRegistry` returned exactly the three read-only
tools, 17 real folders, a formatted search line, and a real message body, with read-only enforced
end to end (EXAMINE + `mark_seen=False`). Two refinements landed (readable-string tool output;
HTML-body fallback), recorded in the [ADR-0009 addendum](adr/ADR-0009-tools-mcp.md). Slice 6
is complete.

## Slice 7 (Subagents)

Delegate narrow tasks to small (2-4B) subagents: task record in the store, each subagent
runs as a stateless function over it, result persisted, cortex consumes it. The cortex
spawns **one or more** subagents and picks their count and size; a bounded CPU budget admits
each spawn. Per the Slice 4 measurements (ADR-0004 addendum) subagents run on **CPU** because the
GPU's 14 GB soft cap is spent on the cortex. The budget here is CPU RAM + acceptable
concurrency, not VRAM.

**Design ([ADR-0010](adr/ADR-0010-subagents.md)):** delegation is a **native
`spawn_subagent` tool** dispatched through Slice 6's audited tool loop (the cortex decides
mid-turn, picking count/size), merged with the MCP tools by a `CompositeToolRegistry`, which is the
first internal-tool seam (ADR-0001 Q2). The bounded infer↔tool loop is extracted from
`TurnEngine` into a shared runner the cortex turn and each subagent both use; subagents are
**tools-enabled but delegation-free** (no `spawn_subagent` in their set), bounding fan-out to
**depth-1**. A subagent is a stateless function over a Redis `TaskStore`. Admission moves to a
dedicated **`SubagentScheduler`** port (bounded CPU concurrency) rather than the GPU
`ModelManager`. ADR-0010 refines the "ModelManager admits or rejects" wording above, since
the two are different resources (exclusive GPU lease vs. counting CPU budget).

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
cortex/subagents and loads the brain (stops their `llama-server` processes, starts the
brain's, per ADR-0005) → brain rehydrates from the store, works, persists → swap back →
cortex resumes from the store. Includes a chaos test (kill a model mid-handoff; system
resumes from the store) and runbook `docs/runbooks/model-swap.md`.
**Gate proven:** THE hard rule, end to end.

## Deferred refinements & later work

Refinements consciously deferred as slices landed. Each is a small change behind an
**unchanged port**, recorded at its origin ADR and collected here so none is lost. Not
ordered; picked up when a slice needs one or on request.

**Tools in Slice 6 ([ADR-0009](adr/ADR-0009-tools-mcp.md)):**
- **Multi-server tool aggregation.** The brain connects to *one* MCP endpoint at a time
  (files *or* email); an `AggregateToolRegistry` fanning `describe`/`invoke` across several
  `McpToolRegistry`s (routing by tool name) lets both coexist behind the unchanged port, per the
  multi-server aggregation addendum.
- **Advertised-tool filtering.** The reference filesystem server advertises write tools the
  read-only mount then `EROFS`-blocks; filtering the advertised set to read tools is a UX
  nicety, not a security need (the mount is the boundary), per the increment-3 addendum.
- **Readable-text-from-HTML extraction.** `read_email` falls back to raw HTML when there is
  no `text/plain` part; a real HTML→text pass would read cleaner, per the increment-4 addendum.
- **Salience / rate policy on the tool loop.** Bounded by `MAX_TOOL_STEPS` today; rate and
  salience limits are a later refinement behind the port (decision 3 / risks).

**Memory in Slice 5 ([ADR-0008](adr/ADR-0008-memory-v1.md)):**
- **Per-session / namespaced scoping.** v1 recall is global across conversations; scoped
  recall is a later refinement behind the same `MemoryStore` port (decision 3).
- **Tiered / self-editing memory + summarization.** Letta's good ideas, adoptable later
  behind the unchanged port (not the framework), per decision 1.
- **ANN index.** Exact cosine now; an approximate index would need a migration, per
  [ADR-0004](adr/ADR-0004-model-lineup.md).

**Inference / Model Manager in Slice 4 ([ADR-0007](adr/ADR-0007-model-manager-inference.md)):**
- **`cortex_model_manager` process lifecycle, co-residency, real swap.** The pure
  single-resident manager exists now; process I/O and swap land in **Slice 11** behind the
  unchanged `ModelManager` port (consequences).
- **MTP (multi-token-prediction) model variants.** Deferred until they earn their keep, per
  [ADR-0004](adr/ADR-0004-model-lineup.md).

**Cross-cutting (originally "Later, unordered"):** pointer-input injection (extend the proto
first), richer memory policies, **email write-actions behind explicit per-action
confirmation** (ADR-0009 risk; Phase-0 assumption 6 below), macOS/Linux OS backends, more
subagent roles.

## Assumptions & risks to confirm (Phase 0)

Deferred *decisions* live in ADR-0001's open questions; these are the *assumptions* the
plan bets on, with what would invalidate each:

1. **VRAM fit.** *Measured in Slice 4 (ADR-0004 addendum).* The soft cap is **14 GB**
   (env `CORTEX_VRAM_SOFT_CAP_GB`, one knob; enforced by the Model Manager from Slice 7). It is
   a deliberate budget: the user reserves the other ~10 GB of the 24 GB GPU for a second
   monitor + gaming. The chosen cortex (gemma-4-12B, QAT Q4) is ~11.3 GB at 16K ctx incl.
   the vision tower, so it sits **comfortably under the cap** (~2.7 GB headroom, since the bump
   from 12 GB buys the always-resident cortex room for KV/context/vision growth). The
   embedder and subagents still run on **CPU**. The GPU budget stays a single-resident
   cortex; the CPU/hybrid split is required by the cap, not an optimization. Context size is
   itself budget-bounded.
2. **Swap latency.** A cortex↔brain swap is a `llama-server` stop + start (ADR-0005),
   so its cost is loading a multi-GB GGUF from the bind-mounted Windows drive.
   Assumed acceptable (seconds, reported to the overlay via the `Converse` status
   stream); if the Windows mount is the bottleneck, hot models get mirrored into a
   WSL-side/volume cache (measured in Slice 4).
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
