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

**Status:** in progress.

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

**Progress (2026-06-29):** CI half landed (increments 1-3), 100% under `just check`, no
GPU/Redis. (1) The pure subagent core: `SubagentTask`/`SubagentResult`, the `TaskStore` +
`SubagentScheduler` ports with the `InMemoryTaskStore` fake and the pure `ConcurrencyScheduler`,
the shared `stream_tool_loop` extracted from `TurnEngine`, and the `SubagentRunner` use-case.
(2) The native `spawn_subagents` tool + `CompositeToolRegistry` (built-in ⊕ MCP), delegation
proven end-to-end over the fakes; the tool is a **concurrent batch** so the CPU budget is
meaningful (ADR-0010 increment-2 addendum). (3) Adapters + wiring: the Redis `RedisTaskStore`
(in `cortex_session`, 100%-covered via fakeredis), the `CORTEX_SUBAGENTS_*` config, `run_from_env`
composition (the cortex gets the composite dispatcher; subagents get the MCP subset, so depth-1),
and `docker-compose.subagents.yml` (a CPU `llama-server` sidecar). (4) The delegation machinery is
**validated on a real CPU `llama-server` running the actual pick, Qwen3.5-2B Q4_K_M** (increment 4;
models are at `/srv/models`): subagents ran concurrently and answered correctly (~893 MiB RSS,
~14.5 s load, ~0.6 s/short answer *with thinking off*), pick locked in the
[ADR-0004 addendum](adr/ADR-0004-model-lineup.md), with an integration test (`test_subagent_live.py`)
and [runbook](runbooks/subagents-cpu.md). Qwen3.5 is a reasoning model (unbounded thinking on CPU
is minutes/call); the dedicated subagent server disables it (`--chat-template-kwargs
'{"enable_thinking": false}'`, baked into `docker-compose.subagents.yml`), so plain requests answer
directly (~0.3-0.6 s) and the live test passes end to end. **Remaining (host GPU half):** the
cortex-driven path (a resident gemma-4-12B *deciding* to emit `spawn_subagents` end to end).

## Slice 8 (Body v1): hotkey → overlay → chat

**Status:** host-validated. Hotkey → overlay → chat runs on Windows; one live-brain stream check remains.

Tauri app skeleton: tray + hidden window, `Hotkey` trait with Windows backend
(macOS/Linux stubs, coverage-off with reasons), overlay shows on hotkey, prompt goes
over `Converse`, streamed reply renders. Configurable hotkey.
**Gate proven:** cfg-gated OS backends; stub coverage escape hatch policy.

**Design ([ADR-0011](adr/ADR-0011-body-v1.md)):** six decisions. One turn per `Converse`
call (session continuity is external, so each prompt is a fresh call sharing the
`session_id`; cancel = drop the stream); a typed `TurnEvent` core mirror of `ServerEvent`
(+ `TransportError::Protocol`); the `Hotkey` port as the first `cfg`-gated OS backend
(Windows real, macOS/Linux `unimplemented!()` stubs behind the coverage escape hatch); the
Windows backend over the `global-hotkey` crate (keeps `unsafe` forbidden); the Tauri app as
a host-native shell **outside** the gated workspace (assumption 4's narrowly-scoped
exclusion); and a React + Vite overlay frontend.

**Progress (2026-07-01):** all four increments are authored; only host validation remains.
CI-gated half (100% under `just check`, no GUI/OS): (1) `BrainTransport::converse` streaming a
typed `TurnEvent` turn, its `body_rpc` adapter over the generated bidi `Converse` (one turn per
call, half-close, `SeamError`→`Failed`, empty/early-close→`Protocol`), and contract tests
scripting the fake brain over loopback. (2) The `Hotkey` OS-backend seam: the port + the pure
`Accelerator::from_chord` chord→`KeyboardEvent.code` mapping in `body_core` (fully tested), and
the `os_linux`/`os_macos` `unimplemented!()` stub crates proving the
`#[cfg_attr(coverage, coverage(off))]` escape-hatch policy ([body-os.md](modules/body-os.md)).
The React overlay is 100%-gated (Vitest, its own path-filtered CI job per the ADR-0006 addendum) and
browser-validated; its `TauriBridge` typechecks against `@tauri-apps/api`.
Host-authored (excluded from CI; Windows validation in [body-overlay.md](runbooks/body-overlay.md)):
(3) the real `os_windows` `global-hotkey` backend behind the `Hotkey` port; (4) the Tauri shell
(`body/app/src-tauri`, `cortex-body`) has tray + hidden window, hotkey → toggle + `cortex:activate`,
the `converse` command streaming `TurnEvent`s to the webview over a Tauri `Channel`
([body-app.md](modules/body-app.md)).
**Host run (2026-07-01):** built + ran `npm run tauri dev` on Windows. The hotkey summons the
overlay, the tray works, and a prompt reaches the brain over IPC→gRPC. A brain-down run surfaced
the "cannot reach the brain" error through the full path, confirming the wiring end to end. Refined
from that run: the window is **transparent** (only the panel floats over the desktop) and the
light/dark toggle moved into the panel header. **Remaining:** one confirmation with the brain up
(`just up-gpu`) to watch a real reply stream token by token. **Deferred overlay polish** (OS-window
morph to a real screen corner, hide-on-blur, click-through on the transparent margins, a tighter
CSP) is recorded in [overlay-ux.md](design/overlay-ux.md) §4 + [body-overlay.md](runbooks/body-overlay.md).

## Slice 8.5 (Resource governance): revise the GPU/CPU managers

**Status:** planned (inserted 2026-07-01; **target: land before Slice 11**, which builds on the
`ModelManager`). Design → ADR-0012 (opens the slice). Inserted as 8.5 to avoid renumbering the
heavily-referenced Slices 9-11.

Revise the `ModelManager` (ADR-0007) and `SubagentScheduler` (ADR-0010) **ports** while they are
still small and pure and before the Slice 11 swap builds on them (retrofitting the swap's
foundation is a rewrite; the same "design the interface around the rule from day one" logic as
the hard rule). Two user-directed motivations:

1. **Subagents are GPU-first, CPU-overflow (not CPU-only)** (corrects ADR-0010 dec 6/7 and
   ADR-0004). The `ModelManager` becomes a **VRAM-budget accountant**: per spawn it fit-tests a
   subagent against the remaining headroom under `CORTEX_VRAM_SOFT_CAP_GB` (cortex + already-
   placed subagents) and places the **whole** model on GPU (`-ngl 99`, allowing **bigger**
   subagents up to ~4B when it fits) or falls back to **CPU-only** (`-ngl 0`), never a partial
   GPU+CPU straddle for a 2-4B (verified worst-of-both-worlds). It owns the accounting rather
   than trusting llama.cpp `--fit` (which sizes to *free* VRAM, not the policy cap). CUDA OOM
   (fails loudly) → re-place on CPU; container OOM → rehydrate from the store (the hard rule).
   The `SubagentScheduler` gains **resource-budget admission** and coordinates with the
   `ModelManager` for placement.

2. **Container-scoped resource caps so the machine stays usable** (verified WSL2 feasibility,
   2026-07-01 research, recorded in [[resource-governance-wsl2]] / ADR-0012):
   - **CPU per subagent:** `--cpus` fractional quota, the user's pick (elastic, per-container,
     touches no WSL-global config).
   - **CPU/RAM global ceiling:** enforced **softly by the `SubagentScheduler`'s admission budget**
     (sum of admitted `--cpus`/`--memory` ≤ target). **No `.wslconfig`, no shared parent cgroup,
     no hard limits on WSL** (user's constraint). RAM per subagent via `--memory` +
     `--memory-swap==--memory`.
   - **GPU compute:** there is **no** per-process GPU-utilization cap on this stack (no MIG on
     consumer GPUs; MPS unusable under WSL2; `nvidia-smi` power/clock host-only + whole-GPU).
     Modeled as a **scheduler concurrency policy** (max concurrent GPU subagents + smaller
     ctx/batch), tuned on the host. The host-side clock clamp is **dropped** (whole-GPU,
     laptop-unreliable, throttles the cortex + games, so not worth it; user + author agreed).

**A deferred option is the Intel NPU (Core Ultra 9 275HX).** Using the otherwise-idle NPU for tiny
subagents/embeddings would fit as a **third `InferenceBackend` adapter** (OpenVINO GenAI, since
llama.cpp has no NPU path) and a third placement target, aligned with "keep the machine usable."
**Needs a feasibility pass before committing.** The NPU **is present** (maintainer confirmed via Task
Manager, 2026-07-01), so the two remaining unknowns are: (a) whether the NPU is reachable from the
dockerized **WSL2** brain, likely the blocker, since WSL2 paravirtualizes the dGPU but not the
NPU, so it may force a host-side runtime that crosses the dockerized-brain seam; (b) whether NPU
LLM inference for 2-4B is fast/mature enough (OpenVINO GenAI).

**Splits (our rhythm):** CI-gated half (me) covers ADR-0012, then the revised `ModelManager` +
`SubagentScheduler` **ports + pure fakes + contract tests** (budget math, fit-test, placement
decision, admission coordination), 100% without a GPU. Host half (user) is per-container cgroup
caps in the compose layering + real GPU-placed-subagent validation, landing the mechanism with
the Slice 11 lifecycle behind the corrected ports.

## Slice 8.7 (Chat history & cycling over the seam)

**Status:** planned (inserted 2026-07-01). Delivers the overlay's deferred multi-chat features
([design/overlay-ux.md §5](design/overlay-ux.md)): store-backed history, listing, and cycling.

The overlay (Slice 8) keeps the current run's chat in memory; persistence across restarts, the
chat switcher, and `Ctrl+↑/↓` cycling need the brain to expose session data over the seam. This
slice extends [proto/body.proto](../proto/body.proto) with read-only `ListSessions` +
`GetSessionMessages` (views of the durable store, as the hard rule keeps sessions safe), threads
them through `BrainService`, grows the `BrainTransport`/`BrainBridge` ports with typed methods +
adapters + contract tests, and switches the overlay's chat list / switcher / cycling to load from
the store instead of memory (brain-generated chat titles may land here too). CI-gated end to end
(fakes both sides, no GPU); the overlay chrome browser-validated. Inserted as 8.7 (decimal insert,
no renumber); independent of the OS-action slices, orderable any time after Slice 8.

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
