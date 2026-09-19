# Cortex architecture

This document maps the system: its components, boundaries, data flow, and the invariants that keep
it workable for agents with small context windows. The rules are in [AGENTS.md](../AGENTS.md) and
the reasoning in [ADR-0001](adr/ADR-0001-architecture.md).

## Components

```
┌─ Windows host ──────────────────────┐   ┌─ Docker (brain, Python) ───────────────────┐
│  Body: one Rust/Tauri process        │   │  orchestrator   routing, handoff, turns    │
│  ├─ overlay webview (show/hide)      │   │  model_manager  owns the GPU, swap queue   │
│  ├─ Hotkey / ScreenCapture /         │gRPC  memory        MemoryStore + Embedder     │
│  │  AudioControl / Notify            │◄──►  tools         MCP servers: email, files  │
│  │  (one backend per OS)             │   │  llama.cpp      serves the loaded models   │
│  └─ rpc: tonic client + server       │   ├────────────────────────────────────────────┤
└──────────────────────────────────────┘   │  Redis (hot state, event bus)              │
                                           │  Postgres + pgvector (durable, vectors)    │
                                           └────────────────────────────────────────────┘
```

- **Body**: one host-native Rust/Tauri process holding the tray, the hidden overlay window, the
  global hotkey, screen capture, audio and volume, notifications and the webview UI. It has **no
  business logic**: OS adapters behind traits, plus a gRPC transport to the brain. It runs on the
  host because those capabilities do not cross the WSL2 or container boundary cleanly.
- **Brain**: dockerized Python services. The **orchestrator** (routing, handoff, tool dispatch; a
  thin service whose logic is in the pure core), the **model manager** (the only user of the GPU),
  the **memory service**, and the **MCP tool servers** (email, files).
- **Stores**: Redis holds hot session and task state and the event bus; Postgres with pgvector
  holds durable data and vector memory. These are what survives a model swap.

## Model tiers and the swap rule

Three tiers share one 24 GB GPU through llama.cpp, one `llama-server` process per loaded model
(ADR-0005).

| Tier | Role | Residency | Budget |
|---|---|---|---|
| Cortex | always-on conversation and routing model, multimodal, 9 to 12B | resident on the GPU | 8.6 GiB reserved, measured 2026-08-07 at the shipped 16K context including the vision tower, under the 14 GB soft cap (ADR-0012 decision 14) |
| Subagents | small 2 to 4B workers for narrow delegated tasks | dynamic pool, **GPU first with CPU overflow** (ADR-0012) | a whole-model fit test against `soft cap − cortex reservation − placed`: on the GPU (`-ngl 99`) when it fits, on the CPU (`-ngl 0`) when it does not, never split; plus a soft CPU and RAM admission budget |
| Brain | large reasoning model, 31B class, for hard problems | loaded on demand | the whole GPU; the other tiers are unloaded |

**The hard rule: state must survive a model swap.** No conversation, task or working state may live
in a model-server process or a KV cache. The handoff runs in four steps:

1. The cortex decides a task needs the brain model, and the orchestrator **writes** the relevant
   context, a handoff record, into the session store.
2. The orchestrator asks the model manager for the brain model. The manager queues the request,
   stops the cortex and subagent `llama-server` processes, and starts the brain model's.
3. The brain model is **loaded from the store alone**, runs, and its results are **written back**
   to the store.
4. The manager swaps back, and the cortex resumes by **reading the brain's output from the store**.
   Nothing is lost, because nothing lived in either model process.

Every agent (a cortex turn, a subagent task, a brain task) is a **stateless function over the
store**, and a model instance can be discarded at any moment.

## Data flow

The hotkey makes the body show the overlay. The user's prompt opens a gRPC `Converse` stream to the
brain, where the orchestrator loads the session from `SessionStore`, recalls memory, routes the turn
(cortex, subagent or a handoff to the brain model) and calls `InferenceBackend` under a
`ModelManager` lease. Tool calls go through `ToolRegistry` over MCP, or through the body's gRPC
service for OS actions. The reply streams back to the overlay, the turn is written to the store, and
memory writes go to pgvector.

## Ports and traits

Contracts come first, before any adapter. Brain-side ports are Python `Protocol`s in
`brain/packages/core`; entries marked *(planned)* have no `Protocol` there yet, and the full shipped
inventory is in [modules/brain-core.md](modules/brain-core.md) and
[ADR-0068](adr/ADR-0068-port-contract-lists.md).

| Port | Contract |
|---|---|
| `InferenceBackend` | One stateless, possibly multimodal completion or stream against a loaded model: no sessions, no retries, no state. The caller holds a `ModelManager` lease. |
| `ModelManager` | The only user of the GPU. `acquire(model_id)` queues, loads, unloads or swaps, and returns a lease; releasing the lease allows eviction. |
| `ModelHost` | The process lifecycle under that manager: start, stop and health-check one `llama-server` per logical model (ADR-0030). |
| `SessionStore` | The source of truth for conversation, task and handoff state: append events, snapshot, reload. Survives swaps and restarts. |
| `MemoryStore` | Long-term retrieval memory: upsert, top-k semantic search, delete. Never backed by a model. |
| `Embedder` | Text to a fixed-dimension vector, stable for a given model version. |
| `ToolRegistry` | List typed tool schemas and invoke one by name with validated arguments. Every invocation is audited. |
| `ToolAuditSink` | Exactly one durable audit record per dispatched tool call (`ToolInvocation`, with the ADR-0013 `trust` provenance and the chat, turn and subagent task it was made for). |
| `Confirmer` | Out-of-band human confirmation of every tool call that needs approval (ADR-0013, revised by ADR-0022: an untainted call is confirmed through the overlay card on the Converse stream, a tainted one is denied outright). It fails closed: no confirmer, a timeout or a dead stream all mean denied. |
| `TaskStore` | Durable subagent task and result records (`put` and `get`); every subagent is a stateless function over it (ADR-0010). |
| `SubagentPlacer` | Fit-test one spawn against the VRAM budget and place the whole model on the GPU or the CPU (`place`, `release`), never split (ADR-0012). |
| `SubagentScheduler` | `admit(request)` under the soft CPU and RAM budget: an over-budget spawn queues, an impossible charge raises (ADR-0012). |
| `HandoffStore` | The turn remainder a handoff writes and the deep model reads back (ADR-0030). |
| `ScheduleStore` | Durable schedules and reminders, claimed under a fencing token (ADR-0025). |
| `PreferenceStore` | Opaque key and value pairs the brain stores for the overlay and never parses (ADR-0032). |
| `BodyGateway` | Host actions called from the brain (capture the screen, get or set volume, notify), implemented by the gRPC client of `BodyService`. |
| `EventBus` *(planned)* | At-least-once pub/sub of typed coordination events: swap requested, tool invoked, turn complete. |
| `Clock` | `now()` and monotonic ticks. The only time source the core may use. |

Host-side traits, in `body/crates/core`:

| Trait | Contract |
|---|---|
| `ScreenCapture` | Read the primary display as **raw BGRA pixels**. Downscaling, encoding and the byte ceiling are pure core beside it, never in the backend (ADR-0029). |
| `AudioControl` | Get and set the master volume in [0.0, 1.0]; mute and unmute. |
| `Hotkey` | Register configurable global hotkeys and emit press events on a channel. |
| `Notify` | Show a native notification, with fixed app labels for untrusted provenance (ADR-0066). |
| `BrainTransport` | Typed async client for the proto services; owns the connection lifecycle and retry. |
| `InputControl` *(planned)* | Inject keyboard text and chords. The `InjectInput` RPC is in the proto; no trait implements it yet. |

## The body to brain boundary

One gRPC file, [proto/body.proto](../proto/body.proto), is the single source of truth. Rust
generates from it with tonic and Python uses the stubs in `brain/packages/seam`. Both sets of stubs
are committed under `_generated/` directories, so a build needs no protoc, and `just proto`
regenerates them (ADR-0003). There are two services: `BrainService`, hosted by the brain, which the
body streams conversation turns to, and `BodyService`, hosted by the body, which the brain calls for
OS actions. **Never in-process FFI**: the language boundary is exactly the process and network
boundary. Python-to-Python boundaries inside the brain use FastAPI and Pydantic v2, and tools use
MCP.

## Platform differences, in exactly two places

1. **The OS backends (Rust)**: one crate per OS behind the traits above, selected by
   `cfg(target_os)`. Windows is implemented (Core Audio through the `windows` crate,
   `global-hotkey`, `xcap`/`scap`, WinRT toasts); macOS and Linux are `unimplemented!()` stubs with
   coverage turned off and an inline reason until they are needed. One binary per OS.
2. **`InferenceBackend`**: llama.cpp (ADR-0005). Engine flags and GPU quirks stay inside the adapter
   and its runbook. llama.cpp also runs on Metal and CPU, so a later move to macOS likely reuses
   this adapter rather than needing a new one.

Everything else (core logic, stores, MCP servers, the compose topology) stays portable:
configuration from the environment only, no hard-coded paths, no OS assumptions in the core.

## Repo map

Entries marked *(planned)* are the target layout; [ROADMAP.md](ROADMAP.md) says which slice adds
each, and [modules/](modules/) holds one contract doc per module.

```
proto/            the body to brain gRPC contract, and the source of truth for it
docs/             ARCHITECTURE.md, index.md, ROADMAP.md, adr/, readings/, modules/,
                  runbooks/, refinements/ and host/ (one file per task plus a generated
                  index), design/, assets/
brain/            Python workspace (uv), dockerized (brain/Dockerfile)
  packages/       core (pure logic + ports), seam (committed gRPC stubs + facade),
                  orchestrator (hosts BrainService), session (Redis SessionStore +
                  TaskStore), inference (llama.cpp InferenceBackend), embedding (llama.cpp
                  CPU Embedder), memory (pgvector MemoryStore), tools (MCP ToolRegistry +
                  audit sink), email (read-only IMAP MCP server), body_client (gRPC client
                  of the body's BodyService), model_manager (one llama-server per model +
                  the ModelHost adapter); subagents live in core and session, which also
                  holds their tasks; (planned) shared
body/             Rust/Tauri workspace, host-native
  crates/         core (pure logic + the Hotkey, AudioControl, ScreenCapture and Notify
                  traits + BrainTransport), rpc (tonic adapter and committed stubs),
                  os_windows (the real Windows backends), os_linux (stub), os_macos (stub)
  app/            React+Vite overlay, tested to 100%, plus its host-native Tauri shell
                  cortex-body, its own workspace, formatted and clippy-checked in CI
scripts/          this repo's own checks, one module per file, written and tested like the
                  rest of the tree. The thirteen cross-tree scans run on every change and the
                  other modules are read by them or run by hand; modules/repo-checks.md says
                  what each one does.
.github/          CI without a GPU, running the same `just` recipes as local dev
justfile          check and check-*; proto, up/down, brain-serve, seam-health, backlog,
                  shuffle, and the measurement recipes turn-cost, envelope-floor,
                  envelope-pairs, switch-tail and image-volumes
docker/           the compose stack, run with `just up` / `just up-gpu`: docker-compose.yml
                  is brain + redis on loopback, and the overrides are gpu (the model-host
                  sidecar, one llama-server child per tier, plus a read-only model mount),
                  modelhost-loopback (host access to its control API), memory
                  (Postgres+pgvector + the CPU embedder), tools and email (MCP sidecars),
                  subagents and subagents-roster (CPU llama-servers), body (points the
                  brain at the host-native body), imap-probe (a local Dovecot for the two
                  answers a refused SELECT can mean); plus postgres/init.sql
```
