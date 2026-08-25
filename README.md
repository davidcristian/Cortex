<div align="center">

<img src="docs/assets/mark.png" alt="Cortex" width="200">

# Cortex

**A personal, local-first AI assistant.**

A host-native Rust/Tauri **body** (global hotkey, overlay, screen capture, OS actions)
talks over gRPC to a dockerized Python **brain** (llama.cpp inference, memory, tools,
subagents). Everything runs on your own hardware, and all state lives in local stores
that survive every model swap.

<img src="docs/assets/overlay-turn.gif" alt="A turn finishing while minimized: the panel has been dismissed into a corner orb that goes on working, and when the reply lands it expands the orb into a corner preview" width="680">

[![inference: 100% local](https://img.shields.io/badge/inference-100%25_local-8b5cf6)](docs/ARCHITECTURE.md)
[![license: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-3b82f6)](LICENSE)

![Rust](https://img.shields.io/badge/Rust-DEA584?logo=rust&logoColor=white)
![Tauri](https://img.shields.io/badge/Tauri-24C8DB?logo=tauri&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![llama.cpp](https://img.shields.io/badge/llama.cpp-EA580C)
![gRPC](https://img.shields.io/badge/gRPC-2E6C8E)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

Local inference · semantic memory · MCP tools · delegated subagents · screen capture ·
durable reminders

[What is Cortex?](#what-is-cortex) · [Features](#features) · [In action](#in-action) ·
[How it works](#how-it-works) · [Quickstart](#quickstart) ·
[Extending Cortex](#extending-cortex) · [Development](#development) ·
[Documentation](#documentation)

</div>

## What is Cortex?

Cortex is a personal assistant that runs entirely on one machine. Pressing
`Ctrl+Alt+Space` raises a translucent overlay over whatever is on screen; a prompt typed
there is answered by a model running on the local GPU, and the reply streams back into
the overlay. Dismissed mid-turn, the overlay collapses into a corner orb that keeps
working and expands again when the reply arrives. The assistant reads email over IMAP,
recalls relevant context from long-term memory, controls OS features, captures the
screen to answer questions about it, and schedules tasks and reminders that fire later.
Any action it cannot undo requires explicit approval in the overlay before it runs.
Inference, memory, and state live on the machine; only tools reach out to external
services.

The system is two processes joined by a single gRPC seam:

- The **body** is a host-native Rust/Tauri process owning everything that must touch the
  OS: the global hotkey, the overlay window, screen capture, audio, native
  notifications. It holds no business logic.
- The **brain** is dockerized Python: the orchestrator, inference through llama.cpp, a
  model manager that owns the GPU, semantic memory over Postgres + pgvector, MCP tool
  servers, and a pool of small delegated subagents.

Cortex is in active development, and the body targets Windows today: its OS
capabilities (the hotkey, audio, screen capture) are Rust traits with real Windows
backends, while macOS and Linux have stubs satisfying the same traits, so a port is a
matter of writing adapters. The brain is a Docker stack and runs anywhere Docker and an
NVIDIA GPU do.

## Features

### Memory

Long-term memory lives in Postgres with pgvector. Facts worth keeping are embedded and
stored as a conversation runs; a later turn fetches candidates by similarity, has a
small model rerank them, and records an audit trail of what was kept and what was
passed over. A question the store cannot help with gets no recall at all instead of the
nearest misses. Conversations are stored the same way, so the overlay's chat list and
history are still there after a restart.

### Tools and actions

Every tool call goes through one audited dispatcher. Files and email arrive as MCP
servers; OS control is a growing suite of internal tools that cross the seam to the
body, with volume, native toasts, and screen capture (aimed at the whole display or at
a single window) as its first members, and each new control rides the same audited
path. Reminders
and scheduled tasks are stored durably and fire through the same path, whether or not
the model that created them is still loaded. An action that cannot be undone, like
sending an email, stops at an approval card in the overlay that shows the exact draft
and sends nothing until it is approved.

### Untrusted content

Anything that arrives through a tool is data, never instructions. It enters the turn
fenced and tracked, a turn that has touched it loses access to every gated tool, and a
link it carried in is redacted if it reappears in the reply. A memory recorded from
such a turn keeps that provenance, and recalling it later fences the new turn too.

### Appearance

The overlay is styled from its console: themes that follow the system, four marks for
the activity bubble (Mull, Muse, Hunch, Tangent), and four window edges (Still, Lucid,
Reverie, Trance) that can send the panel's silhouette liquid. Replies stream in by
condensing like breath on glass, letters clearing along one continuous front. The
choices are stored by the brain as opaque preferences, so they survive a reinstall of
the body.

## In action

Every capture below is the real overlay served by `vite dev` against the demo bridge,
in both of its themes; the pair follows the theme you are reading in.

<table>
<tr>
<td width="33%" align="center" valign="top">
<picture>
<source media="(prefers-color-scheme: dark)" srcset="docs/assets/overlay-reminders-dark.png">
<img src="docs/assets/overlay-reminders-light.png" alt="The overlay on open, with three due reminders stacked above the empty chat; the one that came from untrusted content carries a fenced marker">
</picture>
<br><sub>Due reminders greet the overlay when it opens. The one created from tool-read
content is fenced and says so.</sub>
</td>
<td width="33%" align="center" valign="top">
<picture>
<source media="(prefers-color-scheme: dark)" srcset="docs/assets/overlay-confirm-dark.png">
<img src="docs/assets/overlay-confirm-light.png" alt="The approval card for a gated send_email call, showing the recipient, subject, body, and attachment of the exact draft, with Deny and Approve buttons">
</picture>
<br><sub>A gated send pauses at the approval card, which carries the exact draft
the model wants to send.</sub>
</td>
<td width="33%" align="center" valign="top">
<picture>
<source media="(prefers-color-scheme: dark)" srcset="docs/assets/overlay-console-dark.png">
<img src="docs/assets/overlay-console-light.png" alt="The console's appearance tab, with the theme picker, the four marks Mull, Muse, Hunch, and Tangent, and the four window edges Still, Lucid, Reverie, and Trance">
</picture>
<br><sub>The console holds the appearance registries: the theme, the four marks, and
the four window edges.</sub>
</td>
</tr>
</table>

## The one hard rule

> **State survives a model swap.** Models are loaded and evicted from the GPU at any
> moment; every model instance is stateless and disposable. All conversation, task, and
> working state lives in external stores (Redis for hot state, Postgres for durable
> data) behind ports. A handoff serializes context to the store, swaps processes,
> rehydrates the target, persists results, and swaps back. A chaos suite kills the
> handoff at every step boundary and proves the system converges with nothing lost.

## How it works

```mermaid
flowchart LR
    subgraph body["The body · host-native Rust + Tauri"]
        HK["Global hotkey"] --> OV["Overlay"]
        OS["OS backends<br>audio · capture · toasts"]
    end
    subgraph brain["The brain · dockerized Python"]
        OR["Orchestrator"] --> MM["Model manager"]
        MM --> LL["llama.cpp<br>one server per model"]
        OR --> SA["Subagents"]
        OR --> TO["MCP tools<br>files · email"]
        OR --> ME["Memory"]
    end
    OV -->|"gRPC · Converse"| OR
    OR -->|"gRPC · OS actions"| OS
    OR --- RD[("Redis<br>hot state")]
    ME --- PG[("Postgres + pgvector<br>durable memory")]
```

A turn flows hotkey → overlay → `Converse` stream → the orchestrator, which rehydrates
the session from the store, recalls memory, routes (answer directly, spawn subagents, or
swap in the deep model), dispatches audited tools, and streams the reply back while
persisting everything that must outlive the turn. The whole seam is one `.proto` file,
[proto/body.proto](proto/body.proto), and both sides are generated from it. The full map
lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Models

| Tier | Model | Residency |
|---|---|---|
| **Cortex** | gemma-4-12B, multimodal, QAT Q4 | Resident on the GPU; answers every turn and routes the rest |
| **Subagents** | A 2-4B roster; gemma-4-E4B is the injection-robust default | Spawned per task; placed GPU-first with CPU overflow, never straddling |
| **Brain** | A 31B-class reasoner | Loaded on demand; the resident models are evicted and restored afterwards |

Placement is governed by a soft VRAM budget (`CORTEX_VRAM_SOFT_CAP_GB`, 14 GB on a 24 GB
card) so the machine stays usable beside the assistant. Embeddings run on CPU
(nomic-embed-text-v1.5) and never compete for the GPU.

Cortex is developed on a single laptop: a mobile GPU with 24 GB of VRAM at 175 W,
128 GB of DDR5 RAM at 5600 MT/s, and an Intel Core Ultra 9 275HX. The lineup above is
tuned to that budget rather than hard-coded: every model is a GGUF file named in an env
var, so each tier can be swapped to fit the hardware you actually have.

## Quickstart

Prerequisites: Docker with the NVIDIA container toolkit and a folder of GGUF models for
the brain; Rust (stable), Node, and [`just`](https://github.com/casey/just) for the body.

Point `CORTEX_MODELS_DIR` at your GGUF folder (every knob and the model picks are
walked through in [docs/runbooks/llamacpp-gpu.md](docs/runbooks/llamacpp-gpu.md)),
then:

```bash
# 1. The brain: Redis, orchestrator, and a llama.cpp model host on your GPU
just up-gpu
```

```powershell
# 2. The body: overlay + tray, on the Windows host
cd body\app
npm ci
npm run tauri dev
```

Press `Ctrl+Alt+Space` and type a prompt.

Without a GPU, `just up` starts the brain with a scripted inference backend, and
`cd body/app && npm run dev` serves the overlay in a plain browser against a demo
bridge.

## Extending Cortex

Every capability is a port: a `Protocol` in the pure Python core, or a trait in pure
Rust. The core never imports a backend, an SDK, a network client, or an OS API, so a new
backend is a new adapter and nothing above it changes. Ports come first, with a contract
test and a fake, and the real adapter has to pass the same contract test the fake does.

| Port | What it abstracts | Implementations |
| ---- | ----------------- | --------------- |
| `InferenceBackend` | One stateless streamed completion | llama.cpp over the OpenAI-compatible API · a scripted echo backend for CI |
| `Embedder` | Text to a vector | llama.cpp on CPU · fake |
| `MemoryStore` | Durable semantic memory | Postgres + pgvector · in-memory fake |
| `SessionStore` · `TaskStore` · `ScheduleStore` · `HandoffStore` · `PreferenceStore` | Hot and durable state | Redis · in-memory fakes |
| `ToolRegistry` | The tools a model may call | MCP client (filesystem, email) · built-ins · composite and gated wrappers |
| `ModelHost` · `ModelManager` | One OS process per model, and who owns the GPU | Supervisor sidecar over HTTP · scripted host |
| `BodyGateway` | The brain calling the body | gRPC client of `BodyService` · fake |
| `Confirmer` | Asking the user before an irreversible act | The overlay's approval card over the Converse stream · fake |
| `Hotkey` · `AudioControl` · `ScreenCapture` (Rust) | OS capabilities | Real Windows backends · `cfg`-gated Linux and macOS stubs |

A port is small enough to read in full. This is the whole of one:

```python
class Embedder(Protocol):
    """Turns text into the vector retrieval ranks on (one stateless call, no I/O state)."""

    async def embed(self, text: str) -> Sequence[float]: ...
```

The reasoning behind each seam is recorded in [docs/adr/](docs/adr/).

## Development

`just check` is the single gate: formatting, lints, strict types, tests, and a set of
cross-tree consistency scans, run identically by CI, by the pre-commit hook, and
locally. Design decisions land as ADRs in [docs/adr/](docs/adr/), every module keeps a
short contract doc in [docs/modules/](docs/modules/), and a refinement that is
consciously deferred is written down in [docs/refinements/](docs/refinements/index.md)
instead of lost. Code that touches a real GPU, OS, or network lives in thin adapters
whose live tests are integration-marked and run by hand on the host; CI runs without a
GPU. The full working agreement is [AGENTS.md](AGENTS.md).

## Common commands

| Command | What it does |
| ------- | ------------ |
| `just check` | The whole gate: eight cross-tree scans, then the four trees in parallel |
| `just up` / `just down` | The brain in Compose, with the scripted inference backend |
| `just up-gpu` | The brain plus a llama.cpp model host on the GPU |
| `just brain-serve` | The brain natively, no Docker |
| `just proto` | Regenerate the committed seam stubs from `proto/body.proto` |
| `just image-volumes` | Ask docker what the pinned images declare, against the recorded answer |
| `just seam-health` | Live seam check, dialed from the body side (needs a brain served with a seam token) |
| `just turn-cost` | The A/B/A live measurement of what a change costs a real turn |

## Repository layout

| Path | What lives here |
| ---- | --------------- |
| `proto/` | The body to brain gRPC contract, and the single source of truth for the seam |
| `brain/` | The Python workspace (uv, dockerized): pure core and ports, plus one package per adapter (inference, embedding, memory, session, tools, email, model manager, body client, orchestrator, seam) |
| `body/` | The Rust workspace: pure core with the OS traits, the tonic seam adapter, and per-platform OS backends |
| `body/app/` | The React + Vite overlay and its host-native Tauri shell |
| `docker/` | The Compose stack and its overrides (GPU, memory, tools, email, subagents, body) |
| `scripts/` | The repo gates, each its own module, gated like any other Python here |
| `docs/` | Architecture, ADRs, module contracts, runbooks, the refinements backlog |
| `.github/` | GPU-less CI, running the same `just` recipes as local dev |

## Documentation

| Where | What |
|---|---|
| [docs/index.md](docs/index.md) | The map of everything below |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, boundaries, data flow, the swap rule |
| [docs/adr/](docs/adr/) | Every decision, from the founding architecture to the streaming redesign |
| [docs/modules/](docs/modules/) | One short contract doc per module |
| [docs/runbooks/](docs/runbooks/) | How to bring up and validate each subsystem live |
| [docs/design/overlay-ux.md](docs/design/overlay-ux.md) | The overlay's UX and visual language |
| [docs/refinements/](docs/refinements/index.md) | Every consciously deferred refinement, one file per task |
| [docs/host/](docs/host/index.md) | Work that is built and waiting on hardware this repo is not developed on |
| [docs/ROADMAP.md](docs/ROADMAP.md) | The ordered vertical slices |
| [AGENTS.md](AGENTS.md) | The rules every change in this repo is held to |

## License

Cortex is licensed under the [GNU Affero General Public License v3.0](LICENSE).
