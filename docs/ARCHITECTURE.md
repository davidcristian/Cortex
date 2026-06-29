# Cortex Architecture

The map of the system: components, boundaries, data flow, and the invariants that keep it
maintainable by agents with small context windows. Rules live in
[AGENTS.md](../AGENTS.md); rationale lives in [ADR-0001](adr/ADR-0001-architecture.md).

## Components

```
┌─ Windows host ──────────────────────┐   ┌─ Docker (brain, Python) ───────────────────┐
│  Body: one Rust/Tauri process        │   │  orchestrator   routing, handoff, turns    │
│  ├─ overlay webview (show/hide)      │   │  model_manager  owns the GPU, swap queue   │
│  ├─ Hotkey / ScreenCapture /         │gRPC  memory        MemoryStore + Embedder     │
│  │  AudioControl / InputControl      │◄──►  tools         MCP servers: email, files  │
│  │  (per-OS trait backends)          │   │  llama.cpp      serves the loaded models   │
│  └─ rpc: tonic client + server       │   ├────────────────────────────────────────────┤
└──────────────────────────────────────┘   │  Redis (hot state, event bus)              │
                                           │  Postgres + pgvector (durable, vectors)    │
                                           └────────────────────────────────────────────┘
```

- **Body** is a single host-native Rust/Tauri process: tray + hidden overlay window,
  global hotkey, screen capture, audio/volume, input injection, and the webview UI.
  It holds **no business logic**: OS adapters behind traits, plus a gRPC transport to
  the brain. Runs on the host because those capabilities don't cross the WSL2/container
  boundary cleanly.
- **Brain** is dockerized Python services: the **orchestrator** (routing, handoff, tool
  dispatch; a thin service whose logic is in the pure core), the **model manager** (sole
  user of the GPU), the **memory service**, and **MCP tool servers** (email, files).
- **Stores.** Redis holds hot session/task state and the event bus; Postgres + pgvector
  holds durable data and vector memory. These are what survive model swaps.

## Model tiers and the swap rule

Three tiers share one 24 GB GPU via llama.cpp (ADR-0005; one
`llama-server` process per loaded model):

| Tier | Role | Residency | VRAM |
|---|---|---|---|
| Cortex | always-on conversational + routing model (multimodal, ~9-12B) | resident on GPU | ~11.3 GB, under the 14 GB soft cap (ADR-0004 addendum) |
| Subagents | small (2-4B) workers for narrow delegated tasks | dynamic pool on **CPU** | CPU RAM + concurrency; GPU budget is the cortex's |
| Brain | large reasoning model (~31B-class) for hard problems | loaded on demand | full GPU; others evicted |

**The hard rule: state must survive a model swap.** No conversation, task, or working
state may live in a model-server process or KV cache. Handoff sequence:

1. Cortex decides a task needs the brain; the orchestrator **serializes** the relevant
   context (a handoff record) into the session store.
2. Orchestrator asks the model manager for the brain model; the manager queues the
   request, evicts cortex/subagents (stops their `llama-server` processes), and starts
   the brain's.
3. The brain model is **rehydrated** purely from the store, runs, and its results are
   **persisted** back to the store.
4. The manager swaps back; cortex resumes by **reading the brain's output from the
   store**. Nothing was lost because nothing lived in either model process.

Every agent (cortex turn, subagent task, brain task) is a **stateless function over the
store**. Model instances are disposable at any moment.

## Data flow (primary path)

Hotkey → body shows overlay → user prompt → gRPC `Converse` stream to the brain →
orchestrator loads session from `SessionStore`, retrieves memory, routes (cortex /
subagent / brain handoff), calls `InferenceBackend` under a `ModelManager` lease →
tool calls dispatched via `ToolRegistry` (MCP) or via the body's gRPC surface for OS
actions (brain calls body as a client: capture, volume, input) → response streams back
to the overlay → turn persisted to the store; memory writes go to pgvector.

## Ports and traits (contracts come first, defined before any adapter)

Brain-side ports (Python `Protocol`s in `brain/packages/core`):

| Port | Contract (one line) |
|---|---|
| `InferenceBackend` | Run one stateless (multimodal) completion/stream against a loaded model; no sessions, no retries, no state. Caller must hold a `ModelManager` lease. |
| `ModelManager` | Sole user of the GPU: `acquire(model_id)` queues, performs load/unload/swap, returns a lease; release permits eviction. |
| `SessionStore` | Source of truth for conversation/task/handoff state: append events, snapshot, rehydrate; survives swaps and restarts. |
| `MemoryStore` | Long-term retrieval memory: upsert, top-k semantic search, delete. Never backed by a model. |
| `Embedder` | Text → fixed-dimension vector, stable for a given model version. |
| `ToolRegistry` | Enumerate typed tool schemas; invoke by name with validated args; every invocation is audit-logged. |
| `EventBus` | At-least-once pub/sub of typed coordination events (swap requested, tool invoked, turn complete). |
| `Clock` | `now()` / monotonic ticks. It is the only time source the core may use. |
| `BodyGateway` | Brain-side port for host actions (capture screen, get/set volume, inject input); implemented by the gRPC body client. |

Host-side traits (Rust, in `body/crates/core`):

| Trait | Contract (one line) |
|---|---|
| `ScreenCapture` | Capture a screen/window into encoded image bytes + metadata. |
| `AudioControl` | Get/set master volume in [0.0, 1.0]; mute/unmute. |
| `InputControl` | Inject keyboard text/chords (pointer actions deferred until they land in the proto). |
| `Hotkey` | Register configurable global hotkeys; emit press events on a channel. |
| `BrainTransport` | Typed async client for the proto services; owns connection lifecycle and retry. |

## The seam

The body↔brain contract is one gRPC `.proto`, namely [proto/body.proto](../proto/body.proto),
the single source of truth. Rust uses tonic codegen; Python uses generated stubs shipped
in `brain/packages/seam`. Stubs are committed under `_generated/` dirs on both sides
(hermetic builds with no protoc in CI) and regenerated with `just proto` (ADR-0003).
Two services: `BrainService` (hosted by the brain; the body streams conversation turns
to it) and `BodyService` (hosted by the body; the brain calls it for OS actions).
**Never in-process FFI.** The language boundary is exactly the process/network boundary.
Internal Python↔Python boundaries use FastAPI + Pydantic v2; tools use MCP.

## Portability seams (exactly two)

1. **OS backends (Rust)** are one crate per OS behind the traits above,
   `cfg(target_os)`-gated. Windows is implemented (Core Audio via the `windows` crate,
   `enigo`, `global-hotkey`, `xcap`/`scap`); macOS/Linux are `unimplemented!()` stubs
   (coverage-off with inline reason) until needed. One binary per OS.
2. **`InferenceBackend`** is llama.cpp (ADR-0005; engine flags and GPU quirks stay
   inside the adapter and its runbook, `docs/runbooks/`). llama.cpp also runs
   Metal/CPU, so a later Mac move likely reuses this adapter rather than needing a new
   one.

Everything else (core logic, stores, MCP servers, Compose topology) stays portable:
config via env only, no hard-coded paths, no OS assumptions in the core.

## Layout

See the repo map in [AGENTS.md](../AGENTS.md) and per-module contract docs in
[modules/](modules/). Build order lives in [ROADMAP.md](ROADMAP.md).
